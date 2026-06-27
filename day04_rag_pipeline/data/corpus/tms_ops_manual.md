# TMS 运维异常码手册

## E1001 设备离线超过 72 小时
ChunkID：tms_e1001
异常码：E1001
设备型号：TMS-GD-100 / TMS-GD-200
风险等级：HIGH
现象：设备连续 72 小时没有心跳上报，EMQX 连接状态为 disconnected，最近一次 last_seen 超过三天。
可能原因：现场断电、4G 模组欠费、网关 SIM 卡信号弱、设备主板损坏、EMQX ACL 拒绝连接。
排查：先检查 EMQX client_id 是否仍在线，再检查基站信号和电源电压；如果远程日志为空，必须安排现场检修。
建议：不要直接下发 OTA 或重启脚本；先现场检查电源、网络、硬件，再由值班工程师确认是否恢复上线。批量离线超过 20 台时触发 HITL。

## E1002 OTA 下载超时
ChunkID：tms_e1002
异常码：E1002
设备型号：TMS-GD-100 / TMS-HD-300
风险等级：MEDIUM
现象：OTA 包下载进度长时间停在 60% 以下，设备日志出现 OTA_TIMEOUT 或 download timeout。
可能原因：CDN 节点延迟高、固件包过大、弱网环境、断点续传标记损坏、设备存储空间不足。
排查：检查 CDN 命中率、HTTP 206 断点续传、包体 SHA256、设备剩余空间和区域网络质量。
建议：先选 20 台灰度重试，切换备用 CDN 域名，并要求失败率低于 5% 后再扩大范围。失败率超过 10% 必须 HITL。

## E1003 固件版本不兼容
ChunkID：tms_e1003
异常码：E1003
设备型号：TMS-GD-200
风险等级：HIGH
现象：升级前置校验失败，日志出现 firmware mismatch、board revision denied 或 Android API level not supported。
可能原因：固件包适配了错误板卡，Android 版本低于最低要求，bootloader 分区不匹配。
排查：核对设备 board_id、android_version、firmware_version、灰度包 manifest 和签名证书。
建议：立即阻止升级，冻结该固件包，人工确认适配矩阵后才能恢复灰度。不得自动重试。

## E1004 批量升级失败率过高
ChunkID：tms_e1004
异常码：E1004
设备型号：TMS-GD-100 / TMS-GD-200 / TMS-HD-300
风险等级：HIGH
现象：近 7 天 OTA 失败率超过 10%，同一区域失败设备集中，任务队列出现大量 retry。
可能原因：灰度比例过大、网络区域故障、固件包回源慢、设备版本跨度过大。
排查：按 region、android_version、firmware_version 聚合失败率，检查 CDN 回源、EMQX 下行成功率和任务批次大小。
建议：禁止全量升级，只允许 100 台以内试点；超过 100 台批量操作必须 HITL 审批。

## E1005 脚本执行失败
ChunkID：tms_e1005
异常码：E1005
设备型号：TMS-GD-100
风险等级：HIGH
现象：远程脚本返回 SCRIPT_EXEC_ERROR，stderr 包含 permission denied、timeout 或 checksum mismatch。
可能原因：脚本权限不足、设备 busybox 缺少命令、脚本校验失败、执行时间超过安全窗口。
排查：在沙箱设备复现，核对脚本 SHA256、执行用户、命令白名单和超时时间。
建议：禁止在生产设备直接重试；必须先沙箱复现，通过后再按 10 台以内小批量灰度。

## E1006 EMQX 认证失败
ChunkID：tms_e1006
异常码：E1006
设备型号：TMS-GD-200 / TMS-HD-300
风险等级：MEDIUM
现象：设备 MQTT 连接被拒绝，EMQX 日志出现 bad_username_or_password、acl denied 或 token expired。
可能原因：设备证书过期、token 签名错误、ACL 规则变更、client_id 与租户绑定不一致。
排查：检查证书有效期、JWT 签名密钥版本、EMQX ACL 命中规则和租户映射。
建议：先刷新认证 token，再小批量验证连接恢复；不要跳过 ACL 直接放开全局权限。

## E1007 设备存储空间不足
ChunkID：tms_e1007
异常码：E1007
设备型号：TMS-GD-100
风险等级：MEDIUM
现象：OTA 前置检查提示 no space left，/data 分区剩余空间低于 300MB。
可能原因：日志轮转失败、缓存包未清理、历史升级包残留、业务 APK 临时文件膨胀。
排查：查询 /data、/cache 分区使用率，检查日志目录和 ota_cache 目录。
建议：先执行白名单清理脚本，确认剩余空间超过 800MB 后再重试 OTA；清理脚本失败时转人工。

## E1008 回滚失败
ChunkID：tms_e1008
异常码：E1008
设备型号：TMS-HD-300
风险等级：HIGH
现象：升级失败后未能回滚到上一版本，日志出现 rollback slot invalid 或 boot_count exceeded。
可能原因：A/B 分区状态异常、旧版本包被清理、bootloader 回滚标记损坏。
排查：检查 A/B slot 状态、boot_count、last_successful_version 和 recovery 日志。
建议：停止继续升级，保留现场日志，安排人工恢复；禁止再次下发 OTA。

## E1009 区域 CDN 命中率过低
ChunkID：tms_e1009
异常码：E1009
设备型号：TMS-GD-200
风险等级：MEDIUM
现象：华南或华东区域 OTA 下载慢，CDN hit ratio 低于 80%，回源耗时增加。
可能原因：CDN 预热失败、边缘节点缓存被清理、源站带宽不足、DNS 调度错误。
排查：检查阿里云、腾讯云、网宿 CDN 节点命中率，验证固件包 URL 和 DNS 解析。
建议：先预热固件包并切换备用 CDN，观察 30 分钟后再继续灰度。

## E1010 设备时钟漂移
ChunkID：tms_e1010
异常码：E1010
设备型号：TMS-GD-100 / TMS-HD-300
风险等级：LOW
现象：设备时间与服务器时间偏差超过 10 分钟，导致签名校验、证书校验或日志排序异常。
可能原因：NTP 不可达、RTC 电池异常、设备长时间离线后未同步时间。
排查：检查 NTP 地址、系统时间、证书 not_before/not_after 和最近一次同步记录。
建议：先下发 NTP 同步命令，确认时间恢复后再执行认证或 OTA 操作。

