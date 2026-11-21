# custom/ 目录说明

本目录存放**项目本地私有素材与配置**，不参与图标母版资源。

## 文件

- `config.env.example`：完整配置示例。复制为 `config.env` 后按需要修改；脚本只读取 `config.env`，不会读取本示例。
- `startup_logo.png`（可选）：开机启动图，安装到 main / leanback 的 `drawable-nodpi/startup_logo.png`。
- `mobile_startup.png`（可选）：手机端启动图，安装到 mobile 的 `drawable-nodpi/mobile_startup.png`。

## 注意

- 已有的 `config.env`、`startup_logo.png`、`mobile_startup.png` 请保留，不要被示例文件覆盖。
- 不要把 `.jks`、`local.properties`、Keystore 密码或 Base64 Keystore 内容提交进 Git。
- `EXPECTED_RELEASE_CERT_SHA256` 是公开证书指纹（可入库），但必须来自旧 TANG TV 实际安装的 APK；提取方法见 `tools/get_old_apk_signer.bat` 与根目录 README。
- 本目录下多余的历史备份 `*.py` 会被脚本移入 `.removed-backup/`（该目录已加入 `.gitignore`），不会被删除。
