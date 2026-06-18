# 01 Token经济学

> 目标：彻底搞清楚"一次LLM调用真正花了多少钱"——包括那些Agent开发者最容易忽略的隐藏开销。

---

## 1. 定价模型：输入 vs 输出

### 基本计费单位

| 概念 | 说明 |
|------|------|
| Token | 大约 0.75 个英文单词，1.5 个中文字 |
| Prompt Tokens | 发送给模型的所有内容（输入） |
| Completion Tokens | 模型生成的内容（输出） |

### 为什么输出比输入贵 3-5 倍？

```
输入阶段：GPU 并行处理所有 Prompt Tokens（一次性 forward pass）
输出阶段：自回归生成，每个 Token 都需要一次完整 forward pass
          → N 个输出 Token = N 次 forward pass
          → 计算量随输出长度线性增长
```

**实际定价示例（参考，以官方为准）**

| 模型 | 输入 | 输出 |
|------|------|------|
| DeepSeek V3 | ¥0.001/1K tokens | ¥0.004/1K tokens |
| Qwen-Long | ¥0.0005/1K tokens | ¥0.002/1K tokens |
| GPT-4o | $0.005/1K tokens | $0.015/1K tokens |

**面试话术**：
> "输出Token比输入贵3-5倍，因为生成是自回归的——每生成一个Token都要跑一次完整前向传播，
> 而输入是并行处理的。所以Agent设计要优先控制输出长度，而不只是压缩输入。"

---

## 2. 隐藏Token：Agent开发者的成本黑洞

### 一次完整Agent调用的Token构成

```
┌─────────────────────────────────────────────────────────┐
│                  总计：2400 Tokens                       │
├──────────────────┬──────────────────────────────────────┤
│ 组成部分         │ Token数  │ 是否容易被忽略              │
├──────────────────┼──────────┼─────────────────────────────┤
│ System Prompt    │   500    │ ⚠️  中等（开发初期写很长）  │
│ 对话历史 History │   800    │ 🔥 高（多轮后指数膨胀）     │
│ User Query       │   200    │ ✅ 容易感知                 │
│ Tools Schema     │   600    │ 🔥 极高（最易被忽略）       │
│ Completion输出   │   300    │ ✅ 容易感知                 │
└──────────────────┴──────────┴─────────────────────────────┘
```

### Tools Schema：最大的隐藏杀手

每次调用 LLM 时，如果启用了工具调用，**所有工具的 JSON Schema 都会附加到 Prompt 中**：

```json
// 一个典型工具定义（约 150 tokens）
{
  "type": "function",
  "function": {
    "name": "create_ota_task",
    "description": "创建OTA升级任务，将固件推送到指定设备",
    "parameters": {
      "type": "object",
      "properties": {
        "device_ids": {"type": "array", "items": {"type": "string"}, "description": "设备SN列表"},
        "firmware_version": {"type": "string", "description": "目标固件版本号"},
        "region": {"type": "string", "enum": ["华南", "华东", "华北"]},
        "batch_size": {"type": "integer", "description": "分批数量", "default": 100}
      },
      "required": ["device_ids", "firmware_version"]
    }
  }
}
```

**TMS Agent 有 8 个工具 → 8 × 150 ≈ 1200 tokens 隐藏成本（每次调用！）**

### 对话历史：指数膨胀的定时炸弹

```
第1轮：User(100) + Assistant(200) = 300 tokens
第2轮：History(300) + User(100) + Assistant(200) = 600 tokens
第3轮：History(600) + User(100) + Assistant(200) = 900 tokens
第N轮：N × 300 tokens → 线性增长，实际更糟（因为每轮长度不等）
```

**生产策略**：Context Compression（上下文压缩）
- 保留最近 K 轮完整对话
- 早期对话摘要化（Summary）后注入
- 关键信息（设备ID、故障码）单独存 Redis，不放历史

---

## 3. 成本控制三原则

### 原则一：Pre-flight Token 预检

```python
# 错误做法：事后统计
response = call_llm(messages)
cost = response.usage.total_tokens * price_per_token
# ❌ 钱已经花了，统计没有意义

# 正确做法：请求前估算
estimated_tokens = estimate_tokens(messages) + max_tokens
if estimated_tokens > budget.remaining:
    raise BudgetExceededError("预算不足，拒绝请求")
# ✅ 在花钱前拦截
```

### 原则二：输出长度强制限制

```python
# 不同任务设置不同 max_tokens
TASK_MAX_TOKENS = {
    "device_diagnosis": 500,      # 诊断结论不需要太长
    "ota_plan_generation": 1000,  # 升级计划可以稍长
    "status_query": 200,          # 状态查询极短
    "report_generation": 2000,    # 报告允许较长
}
```

### 原则三：模型分层路由

```
简单查询（设备状态）  → Qwen-7B（¥0.0005/1K）
中等诊断（故障分析）  → DeepSeek-V3（¥0.001/1K）
复杂决策（OTA策略）  → 通义千问-Max（¥0.004/1K）
```

**面试话术**：
> "我的成本控制是三层：请求前Token预检拦截超限，任务级max_tokens限制输出长度，
> 以及按任务复杂度路由到不同价位的模型。实测下来，同样的业务量月成本降低了约60%。"

---

## 4. 手写验证：Token消耗分布计算

> 练习题：TMS 设备批量OTA场景，计算单次调用成本

**输入**：
- System Prompt（角色定义 + 安全约束）：500 tokens
- 工具 Schema × 5 个工具：750 tokens
- 最近 5 轮对话历史：1000 tokens
- 当前用户查询：150 tokens
- **总输入：2400 tokens**

**输出**：
- 诊断结论 + OTA计划：800 tokens

**成本计算（DeepSeek V3）**：
```
输入成本：2400 / 1000 × ¥0.001 = ¥0.0024
输出成本：800  / 1000 × ¥0.004 = ¥0.0032
单次总成本：¥0.0056 ≈ 0.056 分
日100次任务成本：¥0.056
月成本（工作日）：¥0.056 × 22 = ¥1.23
```

**关键洞察**：成本并不贵，但**失控场景**才是问题：
- Agent 死循环：100次调用 → ¥0.56（10分钟内）
- 历史膨胀：第50轮对话，History本身就 5000 tokens

---

## 5. 面试必背结论

1. **输出比输入贵3-5倍**，因为自回归生成 vs 并行处理
2. **Tools Schema是最大隐藏开销**，8个工具 ≈ 1200 hidden tokens/次
3. **Pre-flight预检是刚需**，事后统计无法挽回已花的钱
4. **History是定时炸弹**，必须实现上下文压缩策略
