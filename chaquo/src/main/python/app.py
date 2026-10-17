import requests
import os
import contextlib
import tempfile
import textwrap
from importlib.machinery import SourceFileLoader
import json


def spider(cache, source, file_name=None):
    name = file_name or os.path.basename(source)
    path = cache + '/' + name
    writeFile(path, textwrap.dedent(source).encode())
    name = name.split('.')[0]
    return SourceFileLoader(name, path).load_module().Spider()


def writeFile(path, content):
    # Write to a scratch file and rename it into place.  open(path, 'wb') truncates
    # immediately, so a failure part-way through (for example a full disk) would
    # leave a truncated script behind -- and this is the same cache file that
    # Loader.source() falls back to when the network is unavailable, so the last
    # working copy would be destroyed too.  rename() is atomic, so a reader never
    # observes a half-written script.
    if not isinstance(content, (bytes, bytearray)):
        content = str(content).encode()
    parent = os.path.dirname(path) or '.'
    handle = None
    temp = None
    try:
        os.makedirs(parent, exist_ok=True)
        # A unique scratch name per write: two threads writing the same script must
        # not share one temp file, or their bytes interleave and both lose.
        handle, temp = tempfile.mkstemp(dir=parent, prefix=os.path.basename(path) + '.', suffix='.tmp')
        with os.fdopen(handle, 'wb') as f:
            handle = None
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    except BaseException:
        # Never leave a partial scratch file next to the script we failed to replace.
        if handle is not None:
            with contextlib.suppress(OSError):
                os.close(handle)
        if temp is not None:
            with contextlib.suppress(OSError):
                os.remove(temp)
        raise


REDIRECT_TIMEOUT = 10
REDIRECT_MAX_HOPS = 10


def redirect(url, timeout=REDIRECT_TIMEOUT, maxHops=REDIRECT_MAX_HOPS, verify=True):
    # Manual redirect following, so it needs the two guards requests applies for us:
    # a per-hop timeout (a stalled server used to hang the calling thread forever)
    # and a hop limit (a redirect loop used to recurse until RecursionError).
    # verify defaults to True because each hop target comes from a remote Location
    # header: following those with TLS verification disabled lets a man-in-the-middle
    # choose the next URL.  Callers that genuinely need a self-signed host can pass
    # verify=False explicitly.
    if maxHops < 1:
        raise ValueError('redirect needs maxHops >= 1')
    for _ in range(maxHops):
        rsp = requests.get(url, allow_redirects=False, timeout=timeout, verify=verify)
        location = rsp.headers.get('Location')
        if not location:
            return rsp
        url = location
    raise ValueError(f'too many redirects (limit {maxHops})')


def str2json(content):
    # Deliberately strict: every caller passes JSON that the Java bridge produced, so
    # a decode failure means the contract was broken and must not be swallowed into a
    # silent empty result.  Only the error shape is normalised here, so callers and
    # the diagnostic log get one bounded, payload-free message instead of a raw
    # JSONDecodeError/TypeError running to arbitrary length.
    try:
        return json.loads(content)
    except Exception as error:
        raise ValueError(f'str2json: invalid JSON payload: {error}') from None


def getDependence(ru):
    # getDependence is a WebHTV bridge extension, not part of the TVBox/"cat" Python
    # spider contract.  The bundled base/spider.py supplies a default, but a
    # single-file spider that does not inherit from it has no such attribute, and
    # calling it raises AttributeError inside Spider.init().  PyLoader then degrades
    # the site to an all-empty SpiderNull, so home/category/search silently show
    # nothing.  Treat "not implemented" as "no dependencies".
    # Use getattr rather than try/except AttributeError so a real getDependence()
    # that raises internally still surfaces instead of being swallowed here.
    getter = getattr(ru, 'getDependence', None)
    if getter is None:
        return []
    return getter() if callable(getter) else getter


def getName(ru):
    result = ru.getName()
    return result


def init(ru, extend):
    ru.init(extend)


def homeContent(ru, filter):
    result = ru.homeContent(filter)
    formatJo = json.dumps(result, ensure_ascii=False)
    return formatJo


def homeVideoContent(ru):
    result = ru.homeVideoContent()
    formatJo = json.dumps(result, ensure_ascii=False)
    return formatJo


def categoryContent(ru, tid, pg, filter, extend):
    result = ru.categoryContent(tid, pg, filter, str2json(extend))
    formatJo = json.dumps(result, ensure_ascii=False)
    return formatJo


def detailContent(ru, array):
    result = ru.detailContent(str2json(array))
    formatJo = json.dumps(result, ensure_ascii=False)
    return formatJo


def searchContent(ru, key, quick, pg="1"):
    result = ru.searchContent(key, quick, pg)
    formatJo = json.dumps(result, ensure_ascii=False)
    return formatJo


def playerContent(ru, flag, id, vipFlags):
    result = ru.playerContent(flag, id, str2json(vipFlags))
    formatJo = json.dumps(result, ensure_ascii=False)
    return formatJo


def liveContent(ru, url):
    result = ru.liveContent(url)
    return result


def localProxy(ru, param):
    result = ru.localProxy(str2json(param))
    return result


def action(ru, action):
    result = ru.action(action)
    formatJo = json.dumps(result, ensure_ascii=False)
    return formatJo



def subtitle_init(ru, config):
    result = ru.init(str2json(config) if isinstance(config, str) and config.strip().startswith(('{', '[')) else config)
    return json.dumps(result if result is not None else {"code": 0, "data": {}}, ensure_ascii=False)


def subtitle_search(ru, request):
    result = ru.search(str2json(request))
    return json.dumps(result, ensure_ascii=False)


def subtitle_resolve(ru, request):
    result = ru.resolve(str2json(request))
    return json.dumps(result, ensure_ascii=False)

def destroy(ru):
    ru.destroy()


def run():
    pass


if __name__ == '__main__':
    run()
