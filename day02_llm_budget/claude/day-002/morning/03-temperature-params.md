# 03 Temperature / Top_p：参数原理 + 场景路由矩阵

> 目标：知道每个参数的物理意义，并能针对 TMS/养老/OTT 场景做出正确的参数路由决策。

---

## 1. Temperature：控制"随机性"的旋钮

### 数学原理

LLM 生成下一个 Token 时，先计算每个词的 logits（未归一化得分），再通过 softmax 转成概率分布：

```
原始 logits: [3.2, 2.1, 1.5, 0.8, ...]（对应词汇表中每个词）

标准 softmax：P(token_i) = exp(logit_i) / Σ exp(logit_j)

带 Temperature 的 softmax：P(token_i) = exp(logit_i / T) / Σ exp(logit_j / T)
```

### Temperature 的效果

```
Temperature = 0.0（实际取 → 0，近似 argmax）
  分布：[0.99, 0.005, 0.003, 0.001, ...]
  效果：始终选最高概率词，完全确定性，无随机性
  ⚠️  注意：T=0 本质是 greedy decoding，不同框架实现略有差异

Temperature = 1.0（默认，不缩放）
  分布：[0.60, 0.20, 0.12, 0.05, ...]
  效果：保持原始概率分布，适度随机

Temperature = 2.0（高温）
  分布：[0.28, 0.26, 0.24, 0.22, ...]  ← 趋近均匀分布
  效果：各词概率接近，高度随机，容易"胡说"
```

### 直觉类比

```
Temperature = 0  → 每次都点同一道菜（最稳妥的那个）
Temperature = 1  → 按菜单推荐频率随机点
Temperature = 2  → 闭眼随机翻菜单
```

---

## 2. Top_p（Nucleus Sampling）：控制"词汇范围"的过滤器

### 原理

不是缩放概率分布，而是**截断**：只保留累积概率达到 p 的最高概率词，其余直接排除。

```
完整词汇概率（降序排列）：
词A: 0.45 → 累积 0.45
词B: 0.25 → 累积 0.70
词C: 0.15 → 累积 0.85  ← top_p=0.9 的截断点
词D: 0.08 → 累积 0.93
词E: 0.04 → 累积 0.97
...

top_p = 0.1：只从概率最高的词中选（极保守）
top_p = 0.9：保留概率覆盖90%的词（平衡）
top_p = 1.0：不截断，完整词汇表（与只用 temperature 等价）
```

### Temperature vs Top_p 的关系

- **不是互斥的**，通常配合使用
- Temperature 调整分布的"陡峭程度"（高低峰）
- Top_p 过滤掉尾部的长尾词汇（降低乱码风险）
- **生产推荐**：先用 Temperature 控主随机性，再用 Top_p 做安全截断

```
确定性场景：Temperature=0.0, Top_p=0.1  → 极度收敛
平衡场景：  Temperature=0.3, Top_p=0.7  → 稳定但有灵活性
创意场景：  Temperature=0.7, Top_p=0.9  → 多样性输出
```

---

## 3. 场景路由矩阵（TMS / 养老 / OTT）

### 核心决策原则

```
高确定性需求（诊断、用药、法规）→ 低 Temperature，低 Top_p
高创意需求（报告、文案、总结）   → 高 Temperature，高 Top_p
涉及安全执行（OTA指令、脚本）    → Temperature=0，拒绝任何随机性
```

### 完整路由矩阵

| 场景 | Temperature | Top_p | 理由 | 错误示范 |
|------|-------------|-------|------|---------|
| TMS 设备故障诊断 | **0.0 - 0.2** | **0.1** | 诊断结论必须确定，拒绝幻觉；错误诊断→错误OTA→设备变砖 | T=0.8：同一故障每次诊断不同，运维无所适从 |
| TMS OTA 指令生成 | **0.0** | **0.1** | 指令是命令式的，必须精确；任何随机性都可能生成残缺指令 | T=0.5：固件版本号可能被随机替换 |
| TMS 脚本推送验证 | **0.0** | **0.1** | 脚本语法容不得创意；随机输出破坏脚本结构 | T=0.3：脚本变量名被"创意"替换 |
| 养老用药咨询 | **0.0** | **0.1** | 医疗建议绝对严谨；幻觉在医疗场景是事故 | T=0.7：药物名称可能被"创意"变形 |
| 养老健康风险评估 | **0.1** | **0.2** | 风险评级需要确定性；可允许措辞略有变化 | T=0.9：风险等级每次不同，老人家属困惑 |
| OTT 卡顿根因分析 | **0.2 - 0.3** | **0.5** | 分析框架要稳定，但允许措辞多样化 | T=0.0：分析报告每次一字不差，无法适应不同故障场景 |
| OTT 运营日报生成 | **0.5 - 0.7** | **0.9** | 报告文字可以有文采，结构化字段（数字）必须准确 | T=1.5：报告变成乱文 |
| 多Agent规划（Planner） | **0.2** | **0.5** | 规划要稳健可重现，但需要一定灵活性适应不同场景 | T=0.0：Planner 陷入固定模式，无法处理边缘案例 |

### 代码实现示例

```python
from enum import Enum

class TaskType(str, Enum):
    TMS_DIAGNOSIS = "tms_diagnosis"
    TMS_OTA_COMMAND = "tms_ota_command"
    ELDERLY_MEDICATION = "elderly_medication"
    OTT_DEBUG = "ott_debug"
    OTT_REPORT = "ott_report"

TEMPERATURE_ROUTING = {
    TaskType.TMS_DIAGNOSIS:    {"temperature": 0.1,  "top_p": 0.1},
    TaskType.TMS_OTA_COMMAND:  {"temperature": 0.0,  "top_p": 0.1},
    TaskType.ELDERLY_MEDICATION: {"temperature": 0.0, "top_p": 0.1},
    TaskType.OTT_DEBUG:        {"temperature": 0.2,  "top_p": 0.5},
    TaskType.OTT_REPORT:       {"temperature": 0.6,  "top_p": 0.9},
}

def get_sampling_params(task_type: TaskType) -> dict:
    """根据任务类型返回采样参数，不允许调用方自定义"""
    return TEMPERATURE_ROUTING[task_type]
```

---

## 4. 面试追问：为什么不让用户自己设 Temperature？

**问题**：你为什么要在系统层面固定 Temperature，而不让业务方自己配置？

**答**：
> "在 TMS Agent 中，Temperature 不是偏好问题，是安全问题。
> OTA 指令如果因为 Temperature=0.5 随机生成了错误的固件版本，
> 下发给 1000 台设备后可能全部变砖。
> 所以我把 Temperature 作为任务类型的属性固定在系统层，
> 业务方只能选择'任务类型'，不能直接修改采样参数。
> 这是把安全约束内嵌到架构设计中，而不是依赖调用方的自律。"

---

## 5. 面试必背结论

1. **Temperature 缩放 logit，控制分布陡峭度**；Top_p 截断尾部词汇
2. **诊断/医疗/指令 → T=0，拒绝一切随机性**
3. **报告/文案 → T=0.5-0.7，允许文字多样性**
4. **Temperature 是架构决策，不是用户偏好**——安全场景必须系统层锁定
5. **T=0 ≠ 完全相同输出**，Top_p 和模型更新都会影响结果，T=0 只是"尽量确定"
