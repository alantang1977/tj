"""Bridge-contract tests for chaquo/src/main/python/app.py.

Two groups:
  * getDependence: the chaquo bridge calls it unconditionally during Spider.init().
    A single-file spider that does not inherit base/spider.py has no such attribute, so
    an unguarded call raised AttributeError, PyLoader degraded the site to an all-empty
    SpiderNull, and home/category/search silently rendered nothing.
  * writeFile / redirect / str2json: the three helpers that had no failure guards.
"""

import importlib.util
import io
import os
import shutil
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "main/python"

# app.py imports requests at module scope, but the CI host does not install it.
# Install a stub that records calls so the redirect tests can drive it.


class _Response:
    def __init__(self, headers=None, status_code=200):
        self.headers = dict(headers or {})
        self.status_code = status_code


class _RequestsStub(types.ModuleType):
    """Records every get() call and replays scripted responses."""

    def __init__(self):
        super().__init__("requests")
        self.calls = []
        self.scripted = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.scripted:
            item = self.scripted.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        return _Response()


requests_stub = _RequestsStub()
sys.modules["requests"] = requests_stub

spec = importlib.util.spec_from_file_location("webhtv_app_bridge", SOURCE / "app.py")
assert spec is not None, "cannot build a module spec for app.py"
assert spec.loader is not None, "app.py module spec has no loader"
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class RaisesFromBody(Exception):
    pass


class SpiderWithoutGetDependence:
    """Mirrors a single-file spider that ignores the base class entirely."""

    def __init__(self, extend=""):
        self.extend = extend


class SpiderWithGetDependence:
    def getDependence(self):
        return ["base", "helpers"]


class SpiderWithBrokenGetDependence:
    def getDependence(self):
        raise RaisesFromBody("broken dependency list")


class GetDependenceBridgeTest(unittest.TestCase):

    def test_missing_get_dependence_is_treated_as_no_dependencies(self):
        result = bridge.getDependence(SpiderWithoutGetDependence())
        self.assertEqual([], result)

    def test_missing_get_dependence_does_not_raise_attribute_error(self):
        # The exact regression: Spider.init() calls this before init(), so an
        # AttributeError here blanks the whole site.
        try:
            bridge.getDependence(SpiderWithoutGetDependence())
        except AttributeError as error:
            self.fail(f"missing getDependence must not raise: {error}")

    def test_base_class_default_is_used_when_present(self):
        self.assertEqual(["base", "helpers"], bridge.getDependence(SpiderWithGetDependence()))

    def test_real_get_dependence_errors_are_not_swallowed(self):
        # getattr (not try/except AttributeError) keeps genuine failures visible.
        with self.assertRaises(RaisesFromBody):
            bridge.getDependence(SpiderWithBrokenGetDependence())

    def test_falsy_return_value_is_preserved(self):
        class ReturnsNone:
            def getDependence(self):
                return None

        class ReturnsEmptyTuple:
            def getDependence(self):
                return ()

        # The Java side guards with `if (dependence != null)`, so None must survive.
        self.assertIsNone(bridge.getDependence(ReturnsNone()))
        self.assertEqual((), bridge.getDependence(ReturnsEmptyTuple()))

    def test_non_callable_attribute_is_not_treated_as_a_getter(self):
        # A spider that happens to expose getDependence = [] as data must not be
        # invoked; returning the value keeps it JSON-able for the Java side.
        class DataAttribute:
            getDependence = []

        self.assertEqual([], bridge.getDependence(DataAttribute()))

    def test_bridge_keeps_the_tvbox_method_surface(self):
        # Guard the neighbouring members so a future edit cannot drop one while
        # touching this function.
        for name in ("init", "homeContent", "categoryContent", "detailContent",
                     "searchContent", "playerContent", "liveContent", "action"):
            self.assertTrue(callable(getattr(bridge, name, None)), name)


class WriteFileTest(unittest.TestCase):
    """writeFile must never leave a truncated script in place."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="webhtv-app-")
        self.path = os.path.join(self.dir, "spider.py")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_writes_bytes_and_str(self):
        bridge.writeFile(self.path, b"class Spider: pass")
        with open(self.path, "rb") as f:
            self.assertEqual(b"class Spider: pass", f.read())
        bridge.writeFile(self.path, "class Spider: pass")
        with open(self.path, "rb") as f:
            self.assertEqual(b"class Spider: pass", f.read())

    def test_creates_missing_parent_directory(self):
        nested = os.path.join(self.dir, "a", "b", "spider.py")
        bridge.writeFile(nested, b"x")
        self.assertTrue(os.path.isfile(nested))

    def test_existing_file_survives_a_failed_write(self):
        # The real risk: this cache file is what Loader.source() falls back to when
        # the network is unavailable, so a partial overwrite destroys the last
        # working copy of the script.
        bridge.writeFile(self.path, b"GOOD")
        original_replace = os.replace

        def failing_replace(src, dst):
            raise OSError("disk full")

        os.replace = failing_replace
        try:
            with self.assertRaises(OSError):
                bridge.writeFile(self.path, b"PARTIAL")
        finally:
            os.replace = original_replace
        with open(self.path, "rb") as f:
            self.assertEqual(b"GOOD", f.read(), "previous content must survive")

    def test_failed_write_leaves_no_temp_file_behind(self):
        bridge.writeFile(self.path, b"GOOD")
        original_replace = os.replace
        os.replace = lambda src, dst: (_ for _ in ()).throw(OSError("nope"))
        try:
            with self.assertRaises(OSError):
                bridge.writeFile(self.path, b"PARTIAL")
        finally:
            os.replace = original_replace
        self.assertEqual(["spider.py"], sorted(os.listdir(self.dir)))

    def test_content_is_never_partially_visible(self):
        # A reader must never observe a half-written script: os.replace is atomic.
        bridge.writeFile(self.path, b"OLD")
        bridge.writeFile(self.path, b"NEW")
        with open(self.path, "rb") as f:
            self.assertEqual(b"NEW", f.read())

    def test_concurrent_writers_do_not_corrupt_the_file(self):
        # Every write must use its own scratch file.  A single shared "<path>.tmp"
        # lets two writers interleave bytes and leaves neither copy intact, which
        # would defeat the atomic rename this helper exists for.
        payloads = {tag: tag * 20000 for tag in (b"AAAA", b"BBBB")}
        errors = []

        def writer(tag):
            try:
                for _ in range(4):
                    bridge.writeFile(self.path, payloads[tag])
            except BaseException as error:  # noqa: BLE001 - reported below
                errors.append(error)

        threads = [threading.Thread(target=writer, args=(tag,)) for tag in payloads]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual([], errors)
        with open(self.path, "rb") as f:
            final = f.read()
        self.assertIn(final, payloads.values(), "file must be exactly one writer's payload")
        self.assertEqual(["spider.py"], sorted(os.listdir(self.dir)), "no scratch files left")

    def test_os_error_from_makedirs_is_propagated(self):
        # writeFile must not silently succeed when it cannot create the directory.
        nested = os.path.join(self.dir, "blocked", "spider.py")
        original = os.makedirs
        os.makedirs = lambda *a, **k: (_ for _ in ()).throw(PermissionError("denied"))
        try:
            with self.assertRaises(PermissionError):
                bridge.writeFile(nested, b"x")
        finally:
            os.makedirs = original
        self.assertFalse(os.path.exists(nested))


class RedirectTest(unittest.TestCase):
    """redirect follows Location manually, so it needs its own guard rails."""

    def setUp(self):
        requests_stub.calls = []
        requests_stub.scripted = []

    def test_returns_response_when_there_is_no_location(self):
        requests_stub.scripted = [_Response({})]
        rsp = bridge.redirect("https://example.test/a")
        self.assertEqual({}, rsp.headers)
        self.assertEqual(1, len(requests_stub.calls))

    def test_follows_location_until_the_final_response(self):
        requests_stub.scripted = [
            _Response({"Location": "https://example.test/b"}),
            _Response({"Location": "https://example.test/c"}),
            _Response({}),
        ]
        rsp = bridge.redirect("https://example.test/a")
        urls = [url for url, _ in requests_stub.calls]
        self.assertEqual(["https://example.test/a", "https://example.test/b",
                          "https://example.test/c"], urls)
        self.assertEqual({}, rsp.headers)

    def test_every_hop_carries_a_timeout(self):
        # Previously there was no timeout at all: one stalled server hung the
        # calling thread indefinitely.
        requests_stub.scripted = [_Response({"Location": "https://example.test/b"}), _Response({})]
        bridge.redirect("https://example.test/a")
        for url, kwargs in requests_stub.calls:
            self.assertIn("timeout", kwargs, url)
            self.assertEqual(bridge.REDIRECT_TIMEOUT, kwargs["timeout"], url)

    def test_redirect_loop_is_bounded_instead_of_recursing(self):
        # A server redirecting to itself used to recurse until RecursionError.
        requests_stub.scripted = [_Response({"Location": "https://example.test/loop"})
                                  for _ in range(bridge.REDIRECT_MAX_HOPS + 5)]
        with self.assertRaises(ValueError) as caught:
            bridge.redirect("https://example.test/loop")
        self.assertIn("too many redirects", str(caught.exception))
        self.assertEqual(bridge.REDIRECT_MAX_HOPS, len(requests_stub.calls))

    def test_tls_verification_is_on_by_default(self):
        # Each hop target comes from a remote Location header, so following it with
        # verification disabled would let a man-in-the-middle choose the next URL.
        requests_stub.scripted = [_Response({})]
        bridge.redirect("https://example.test/a")
        self.assertIs(True, requests_stub.calls[0][1]["verify"])

    def test_caller_can_opt_out_of_verification_explicitly(self):
        requests_stub.scripted = [_Response({})]
        bridge.redirect("https://self-signed.test/a", verify=False)
        self.assertIs(False, requests_stub.calls[0][1]["verify"])

    def test_hop_limit_must_be_positive(self):
        with self.assertRaises(ValueError):
            bridge.redirect("https://example.test/a", maxHops=0)

    def test_custom_timeout_is_honoured(self):
        requests_stub.scripted = [_Response({})]
        bridge.redirect("https://example.test/a", timeout=3)
        self.assertEqual(3, requests_stub.calls[0][1]["timeout"])


class Str2JsonTest(unittest.TestCase):
    """str2json stays strict, but its error must be bounded and payload-free."""

    def test_parses_valid_json(self):
        self.assertEqual({"a": [1, 2]}, bridge.str2json('{"a": [1, 2]}'))

    def test_accepts_bytes(self):
        self.assertEqual({"a": 1}, bridge.str2json(b'{"a": 1}'))

    def test_invalid_payload_raises_value_error_not_raw_decode_error(self):
        with self.assertRaises(ValueError):
            bridge.str2json('{"list": [')

    def test_error_message_does_not_echo_the_payload(self):
        # The message reaches Result.error() and the diagnostic log, so a long
        # payload could otherwise be copied into both.
        secret = "TOKEN-" + "z" * 200
        with self.assertRaises(ValueError) as caught:
            bridge.str2json("<html>" + secret)
        message = str(caught.exception)
        self.assertNotIn(secret, message)
        self.assertLess(len(message), 300, "error text must stay bounded")

    def test_file_like_input_is_rejected_explicitly(self):
        # io.StringIO used to surface as a bare TypeError from json.loads.
        with self.assertRaises(ValueError):
            bridge.str2json(io.StringIO('{"a": 1}'))

    def test_none_still_fails_loudly(self):
        # Strictness is intentional: callers pass JSON produced by the Java bridge,
        # so a decode failure means the contract was broken.
        with self.assertRaises(ValueError):
            bridge.str2json(None)

    def test_bridge_helpers_are_importable_by_remote_scripts(self):
        for name in ("writeFile", "redirect", "str2json", "spider"):
            self.assertTrue(callable(getattr(bridge, name, None)), name)


if __name__ == "__main__":
    unittest.main()
