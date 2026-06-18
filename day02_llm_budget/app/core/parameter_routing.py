from dataclasses import dataclass
from enum import StrEnum


class TaskType(StrEnum):
    TMS_DIAGNOSIS = "tms_diagnosis"
    ELDERLY_MEDICATION = "elderly_medication"
    OTT_REPORT = "ott_report"


@dataclass(frozen=True)
class SamplingParameters:
    temperature: float
    top_p: float
    rationale: str


PARAMETER_ROUTES = {
    # 运维诊断要求稳定和可复现，尽量压低随机性。
    TaskType.TMS_DIAGNOSIS: SamplingParameters(
        temperature=0.1,
        top_p=0.1,
        rationale="Stable diagnostic output with low variance",
    ),
    # 医疗/用药咨询属于高风险场景，禁止发散式生成。
    TaskType.ELDERLY_MEDICATION: SamplingParameters(
        temperature=0.0,
        top_p=0.1,
        rationale="High-risk domain; minimize creative variation",
    ),
    # 运营报告允许一定表达变化，但事实数据仍应来自结构化输入。
    TaskType.OTT_REPORT: SamplingParameters(
        temperature=0.6,
        top_p=0.9,
        rationale="Allow bounded variation for report generation",
    ),
}


def parameters_for(task_type: TaskType) -> SamplingParameters:
    # 上层只传业务任务类型，参数路由集中管理，便于审计和回滚。
    return PARAMETER_ROUTES[task_type]
