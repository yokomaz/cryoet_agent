# CryoET-Agent 科研想法分析

## 核心问题

这个项目可以被定义成一个科研问题，而不仅仅是一个工程工具：

> 一个结合 cryo-ET 领域知识的大语言模型 agent，能否从原始数据出发，自主选择工具、设置参数、执行处理流程，并通过质量反馈优化 workflow，最终达到接近人类专家设计流程的重构质量？

换句话说，这个项目研究的是：大语言模型 agent 是否能够在 cryo-electron tomography（cryo-ET）数据处理中承担一部分科学决策工作，包括工具选择、参数设置、执行监控、质量评估和迭代优化。

## 背景动机

传统 cryo-ET 数据处理高度依赖人类专家经验。一个科学家通常需要在很长的 pipeline 中不断选择工具和参数：

```text
raw frames
-> motion correction
-> frame averaging
-> tilt-series alignment
-> tomogram reconstruction
-> particle picking
-> subtomogram extraction / averaging
-> FSC calculation
```

每一步都包含非平凡的决策：

- motion correction 应该使用 Warp、MotionCor3、RELION，还是其他工具？
- tilt-series alignment 和 reconstruction 应该使用 IMOD、AreTomo，还是其他软件？
- binning、patch size、dose weighting、tilt range、reconstruction thickness、particle box size 应该如何设置？
- 如果中间结果质量不好，应该回到哪一步重跑？
- 最终结果应该如何评估：FSC、alignment residual、CTF quality、particle count，还是其他指标？

这个研究想法的核心，是用一个闭环的大语言模型 agent 替代或辅助一部分专家决策过程。

## 更稳妥的论文表述

不要一开始就声称“大语言模型比人类专家更会处理 cryo-ET 数据”。这个 claim 太强，也很容易被攻击。原因包括：

- 人类专家流程不一定是全局最优；
- FSC 本身不能完全代表科学质量；
- 不同工具链之间可能并不完全公平；
- agent 可能只是做了参数搜索，而不是真的具备科学理解；
- 数据集数量如果不够，结论很难泛化。

更稳妥、也更容易被审稿人接受的 claim 是：

> 一个结合领域知识和质量反馈的大语言模型 agent，可以自主执行 cryo-ET 预处理流程，并在减少人工干预的同时达到接近专家流程的重构质量。

如果某些数据集上 agent 的 FSC 超过了专家流程，可以把它作为实验发现，而不要把“超过专家”作为论文唯一核心主张。

## 推荐系统设计

这个 agent 不应该只是一个“生成 shell 命令的聊天机器人”，而应该被设计成一个闭环科学 workflow 系统：

```text
用户目标 + 原始数据
        |
        v
LLM Workflow Planner
  - 判断当前数据状态
  - 选择处理步骤
  - 选择工具
  - 提出初始参数
        |
        v
Execution Engine
  - 运行 Warp / MotionCor3 / IMOD / AreTomo / RELION / Dynamo 等工具
  - 捕获日志
  - 记录命令、参数、版本、输入和输出
        |
        v
Quality Evaluator
  - alignment residual
  - CTF confidence
  - MRC statistics
  - particle count and distribution
  - FSC curve and resolution
        |
        v
LLM Controller
  - 接受当前结果
  - 修改参数
  - 重跑失败或低质量步骤
  - 在达到目标质量后停止
```

这里最重要的一点是：LLM 不应该只凭模糊的自然语言描述判断图像质量。它应该读取由程序化 evaluator 产生的结构化质量指标，然后基于这些指标做决策。

例如，quality feedback 可以长这样：

```json
{
  "alignment_residual": 2.8,
  "ctf_confidence": "low",
  "fsc_0143_resolution": "18.5 A",
  "num_particles": 1240,
  "warnings": [
    "large tilt gap",
    "high drift at high tilt"
  ]
}
```

基于这些反馈，agent 可以决定：

- 是否排除高倾角图像；
- 是否调整 alignment 参数；
- 是否修改 reconstruction thickness；
- 是否改变 particle picking threshold；
- 是否重新进行 CTF estimation；
- 是否接受当前结果并停止。

## 可以提出的研究问题

论文可以围绕四个 research questions 展开。

### RQ1: Workflow 决策能力

给定 raw frames、metadata 和目标输出，LLM agent 能否选择合理的 cryo-ET 数据处理流程？

### RQ2: 参数选择能力

Agent 选择的参数是否接近专家参数？是否比工具默认参数更好？

### RQ3: 闭环优化能力

质量反馈是否能够改善最终结果？闭环 agent 是否优于一次性生成 workflow 的 LLM？

### RQ4: 最终科学质量

Agent 最终得到的 reconstruction 或 subtomogram average，是否在 FSC 和其他质量指标上接近专家 pipeline？

## 实验设计

关键是要把 closed-loop agent 和有意义的 baseline 进行比较。

### Baseline 设置

1. **Human expert pipeline**
   - 使用论文中发表的流程，或者由人类专家整理的工具和参数。
   - 这个 baseline 是 reference，不一定是完美 oracle。

2. **Default tool pipeline**
   - 使用同样的工具，但采用默认参数或固定模板参数。
   - 用来衡量专家或 agent 的决策到底带来了多少提升。

3. **Static LLM pipeline**
   - LLM 只生成一次 workflow 和参数。
   - 不根据中间结果进行反馈调整，也不重跑。

4. **Closed-loop LLM agent**
   - 完整系统：规划、执行、质量评估、参数调整和迭代重跑。

### 评估指标

FSC 应该是核心指标，但不应该是唯一指标。

推荐指标包括：

- FSC 0.143 resolution；
- FSC 0.5 resolution；
- alignment residual；
- CTF fitting confidence；
- retained particle number；
- particle spatial distribution；
- tomogram SNR 或 contrast proxy；
- manual intervention count；
- failed run count；
- total compute time；
- parameter trial number。

### 重要注意点

FSC 单独使用可能会有误导性，因为它可能受到 mask、particle selection bias、overfitting 或不同处理习惯的影响。因此，所有方法的 FSC 计算必须标准化，而且最好配合其他质量指标一起分析。

## 数据集策略

第一版不建议试图覆盖所有 cryo-ET workflow。更稳妥的方式是先做一个小而受控的 benchmark。

推荐范围：

- 3 到 5 个公开 cryo-ET 数据集；
- 数据集最好有发表论文 workflow 或专家处理记录；
- raw frames 或 tilt series 可获得；
- 目标输出可以是 tomogram、particles、subtomograms 或 FSC curves；
- 如果完整处理成本太高，可以先使用数据子集。

如果从 raw frames 到 FSC 的完整流程太重，可以先从更窄的任务开始：

- raw frames -> reconstructed tomogram；或者
- tilt series -> tomogram -> particle extraction -> FSC。

等闭环系统稳定后，再逐步扩展 benchmark 的覆盖范围。

## 必要消融实验

为了证明这个系统不是“简单调用工具”，论文中应该加入消融实验：

- 去掉 LLM，只使用固定模板 pipeline；
- 去掉 quality feedback，只使用一次性 planning；
- 去掉 domain skills，只使用通用 LLM；
- 去掉 dataset state inspection；
- 去掉 tool availability checking；
- 限制 parameter search budget。

如果完整系统明显优于这些消融版本，就可以说明领域 grounding 和闭环反馈确实是关键贡献。

## 当前项目需要补的工程模块

当前项目主要还是一个 planner。要支撑这个研究想法，需要新增几个核心模块。

### 1. Workflow Executor

把结构化 plan 转换成真实可执行命令，调用 Warp、MotionCor3、IMOD、AreTomo、RELION、Dynamo 等工具。

### 2. Provenance Logger

记录每一步处理过程：

- command；
- parameters；
- input files；
- output files；
- software version；
- runtime；
- logs；
- errors。

这对可复现性、debug 和论文实验都非常重要。

### 3. Quality Evaluator

自动解析或计算：

- alignment residuals；
- CTF scores；
- MRC header 和 image statistics；
- particle statistics；
- FSC curves；
- tool log 中的 warning signals。

### 4. Closed-Loop Controller

根据质量指标决定是否接受结果、重试当前步骤，或修改参数后重新运行。

### 5. Parameter Search Space

为每个处理步骤定义有边界的、领域相关的参数搜索空间。不能让 LLM 不受限制地随意编造参数。

例子包括：

- motion correction patch size；
- dose weighting；
- binning；
- alignment strategy；
- tilt exclusion；
- reconstruction thickness；
- particle picking threshold；
- subtomogram box size。

### 6. Benchmark Harness

在同一套评估协议下运行 expert、default、static LLM 和 closed-loop LLM 四种 pipeline。

## 可能的论文贡献

一篇比较完整的论文可以主张以下贡献：

1. 将 autonomous cryo-ET workflow execution 定义为一个 quality-guided agent 问题。
2. 提出一个 domain-grounded LLM agent，能够选择工具、配置参数、执行 workflow，并使用质量反馈进行迭代优化。
3. 构建一个 benchmark，用来比较 expert pipeline、default pipeline、static LLM planning 和 closed-loop LLM execution。
4. 实验证明闭环反馈和领域 grounding 可以提升重构质量，或者减少人工干预。

## 建议的论文主张

一个保守但可防守的主 claim：

> 我们证明，一个结合 cryo-ET 领域知识和质量反馈的大语言模型 agent，可以自主执行 cryo-ET 预处理流程，并在减少人工干预的同时达到接近专家设计 pipeline 的重构质量。

如果实验结果足够强，可以加入更强的 claim：

> 在部分数据集上，agent 通过探索替代参数设置，在标准化评估协议下获得了优于发表专家流程的 FSC 分辨率。

## 总结

这是一个成立且有潜力的科研方向。它的核心不是简单地用 LLM 生成 shell 命令，而是研究 LLM agent 是否能够作为科学数据处理中的决策系统：

- 选择工具；
- 设置参数；
- 解释中间质量信号；
- 修正失败步骤；
- 优化最终重构质量；
- 生成可复现的处理记录。

如果系统停留在一次性命令生成，论文会比较弱。  
如果系统被做成一个闭环的、质量驱动的 cryo-ET processing agent，并且和专家 workflow 进行系统比较，这就可以成为一个有力的科研项目。
