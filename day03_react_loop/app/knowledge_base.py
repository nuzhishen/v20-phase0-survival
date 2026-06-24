from dataclasses import dataclass

from app.react_types import RiskLevel


@dataclass(frozen=True)
class ErrorKnowledge:
    error_code: str
    root_cause: str
    recommended_action: str
    default_risk: RiskLevel


TMS_ERROR_KNOWLEDGE: dict[str, ErrorKnowledge] = {
    "OTA_TIMEOUT": ErrorKnowledge(
        error_code="OTA_TIMEOUT",
        root_cause="OTA 下载或安装超时",
        recommended_action="检查网络与 CDN 状态，先小批量灰度重试",
        default_risk="MEDIUM",
    ),
    "DEVICE_OFFLINE": ErrorKnowledge(
        error_code="DEVICE_OFFLINE",
        root_cause="设备离线",
        recommended_action="暂缓 OTA，等待设备恢复在线",
        default_risk="MEDIUM",
    ),
    "FIRMWARE_MISMATCH": ErrorKnowledge(
        error_code="FIRMWARE_MISMATCH",
        root_cause="固件版本不兼容",
        recommended_action="阻止升级，人工确认固件包",
        default_risk="HIGH",
    ),
    "HIGH_FAILURE_RATE": ErrorKnowledge(
        error_code="HIGH_FAILURE_RATE",
        root_cause="近 7 天失败率过高",
        recommended_action="先 100 台试点，不允许全量",
        default_risk="HIGH",
    ),
    "SCRIPT_EXEC_ERROR": ErrorKnowledge(
        error_code="SCRIPT_EXEC_ERROR",
        root_cause="脚本执行失败",
        recommended_action="沙箱复现，禁止直接重试",
        default_risk="HIGH",
    ),
}


UNKNOWN_ERROR_FALLBACK = "UNKNOWN_ERROR_CODE_REQUIRE_MANUAL_CHECK"


def get_error_knowledge(error_code: str) -> ErrorKnowledge | None:
    return TMS_ERROR_KNOWLEDGE.get(error_code)
