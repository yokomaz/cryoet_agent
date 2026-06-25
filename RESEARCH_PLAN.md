# CryoET-Agent 科研计划

> 目标期刊: Nature Methods / Nature Computational Science / Bioinformatics (根据实验结果调整)

---

## 一、核心科研命题

> 一个结合 cryo-ET 领域知识和质量反馈的大语言模型 agent，可以自主执行 cryo-ET 预处理流程，并在减少人工干预的同时达到接近专家设计 pipeline 的重构质量。

**创新点：** 不是 LLM 生成 shell 命令，而是 LLM 作为科学决策系统 — 选择工具、设置参数、解读质量信号、修正失败步骤、优化最终质量。

---

## 二、阶段划分与里程碑

### Phase 1: Engineering Foundation (第 1-2 月)
**目标：把 planner 升级为 closed-loop executor**

#### 1.1 Workflow Executor（工作流执行引擎）
- [ ] 将结构化 plan (JSON workflow) 翻译为可执行命令
- [ ] 支持串行步骤执行：motion correction → CTF → alignment → reconstruction → particle picking → subtomogram averaging
- [ ] 每个步骤执行完成后收集 stdout/stderr/logs
- [ ] 步骤间数据流管理（上游输出自动成为下游输入）
- [ ] 错误处理：步骤失败时捕获错误，不中断整个 pipeline

**涉及工具：** Warp, MotionCor3, IMOD, AreTomo, RELION, Dynamo

#### 1.2 Provenance Logger（溯源记录器）
- [ ] 记录每一步的完整 provenance 信息：
  - 命令 (exact shell command)
  - 参数 (key=value)
  - 输入文件 (SHA256 hash)
  - 输出文件 (SHA256 hash)
  - 软件版本 (e.g., `MotionCor3 --version`)
  - 运行时间 (wall clock)
  - stdout/stderr 完整日志
  - 退出码
- [ ] 输出格式：JSONL（每行一个步骤），方便实验分析
- [ ] 生成可复现脚本（从 provenance log 重建所有命令）

#### 1.3 Quality Evaluator（质量评估器）
- [ ] 解析 alignment log，提取 alignment residual
- [ ] 解析 CTF output (Gctf/CTFFIND4)，提取 CTF max resolution、confidence
- [ ] 读取 MRC header 和 image statistics（mean, std, min, max per slice）
- [ ] 统计 particle count 和 spatial distribution
- [ ] 计算 FSC curve（需要 gold-standard 半集重构，或使用现有工具）
- [ ] 解析工具 log 中的 warning signals（drift, tilt gap 等）
- [ ] 输出标准化 JSON quality report（如 RESEARCH_IDEA.md 中定义的格式）

**关键：** Quality Evaluator 必须是程序化的（解析数字和日志），而不是让 LLM "看图判断质量"。

#### 1.4 Parameter Search Space（参数搜索空间定义）
- [ ] 为每个处理步骤定义 bounded 参数空间：
  ```python
  MOTION_CORRECTION_PARAMS = {
      "patch_size": {"type": "int", "range": [4, 16], "step": 2},
      "dose_weighting": {"type": "bool"},
      "binning": {"type": "float", "options": [0.5, 1.0, 2.0]},
  }
  ALIGNMENT_PARAMS = {
      "tilt_exclusion": {"type": "list[float]", "description": "tilt angles to exclude"},
      "alignment_strategy": {"type": "enum", "options": ["patch_tracking", "fiducial"]},
      "binning": {"type": "float", "options": [2.0, 4.0, 8.0]},
  }
  ```
- [ ] LLM 只能在这个 bounded 空间内选择参数（不能随意编造）
- [ ] 每个参数有领域相关的默认值和推荐范围

#### 1.5 Closed-Loop Controller（闭环控制器）
- [ ] 核心循环逻辑：
  ```
  for step in workflow:
      execute(step)
      quality = evaluate(step.output)
      while not acceptable(quality) and retries < max_retries:
          new_params = llm_suggest(step, quality, param_space)
          execute(step, new_params)
          quality = evaluate(step.output)
          retries += 1
      if retries >= max_retries:
          flag_as_failed(step)
  ```
- [ ] LLM Controller 的输入：当前步骤、质量报告 JSON、参数空间、重试历史
- [ ] LLM Controller 的输出：新的参数组合（在 param_space 范围内）
- [ ] 实现 max_retries 限制（防止无限循环）
- [ ] 实现 early stopping（达到目标质量后停止）

---

### Phase 2: Benchmark Construction (第 2-3 月，可与 Phase 1 后期并行)
**目标：构建可复现的实验评估框架**

#### 2.1 Dataset Selection（数据集选择）
- [ ] 选择 3-5 个公开 cryo-ET 数据集，条件：
  - Raw frames 或 tilt series 可获取（EMPIAR/EMDB）
  - 有已发表论文的处理 workflow（用于 expert baseline）
  - 覆盖不同样本类型（in vitro, in situ/cellular）
  - 覆盖不同数据采集策略（dose-symmetric, bidirectional 等）
- [ ] 推荐候选数据集：
  1. EMPIAR-10164 (S. cerevisiae ribosomes, dose-symmetric)
  2. EMPIAR-10499 (HIV-1 CA-SP1, in vitro)
  3. EMPIAR-10986 (S. pombe nuclear pore complex, in situ)
  4. EMPIAR-10760 (Human proteasome, 不同 defocus 条件)
  5. 根据实际情况选择更多

#### 2.2 Benchmark Harness（基准测试框架）
- [ ] 统一的评估协议：
  - 所有方法使用相同的输入数据
  - 所有方法使用相同的 FSC 计算脚本（标准化 mask, pixel size, box size）
  - 所有方法在相同硬件上运行
- [ ] 实现四种 pipeline 的运行入口：
  1. **Expert pipeline**: 固定参数，来自已发表论文
  2. **Default pipeline**: 相同工具，全部默认参数
  3. **Static LLM**: LLM 一次性生成 workflow + 参数，不迭代
  4. **Closed-loop LLM**: 完整的规划→执行→评估→调整循环
- [ ] 自动收集所有 metrics：FSC 0.143, FSC 0.5, alignment residual, CTF confidence, particle count, compute time, failed run count, parameter trial count, manual intervention count

#### 2.3 Baseline Implementation（基线实现）
- [ ] Expert pipeline: 严格按照已发表论文的 methods 章节配置参数
- [ ] Default pipeline: 使用每个工具的默认参数（`motioncor3 --default` 等）
- [ ] Static LLM pipeline: 复用现有 planner，但只生成一次 plan 即执行
- [ ] Closed-loop LLM: Phase 1 构建的完整系统

---

### Phase 3: Experiments & Ablation (第 3-5 月)
**目标：回答四个研究问题 (RQ1-RQ4)**

#### 3.1 RQ1 — Workflow 决策能力
- 实验：给 agent raw frames + metadata + 目标输出，agent 选择工具链
- 评估：agent 选择的工具链是否与专家流程一致？
  - 完全匹配 (exact match)
  - 功能等价 (functional equivalence)
  - 明显错误 (明显不合理的选择)
- 对比：Static LLM vs Closed-loop LLM

#### 3.2 RQ2 — 参数选择能力
- 实验：固定工具链，agent 选择参数 vs 专家参数 vs 默认参数
- 评估：agent 参数与专家参数的距离（normalized parameter distance）
- 最终质量对比：FSC resolution, particle count

#### 3.3 RQ3 — 闭环优化能力
- 实验：相同初始 workflow，有无质量反馈循环
- 版本：Static LLM（一次性）vs Closed-loop LLM（迭代优化）
- 评估：FSC 改善幅度、失败步骤修复率、参数调整次数

#### 3.4 RQ4 — 最终科学质量
- 实验：四种 pipeline 在所有数据集上的完整对比
- 主指标：FSC 0.143 resolution
- 辅助指标：FSC 0.5, alignment residual, CTF confidence, particle count, compute time, 人工干预次数
- 统计分析：paired t-test 或 Wilcoxon signed-rank test across datasets

#### 3.5 消融实验（Ablation Studies）
- [ ] 去掉 LLM（只用固定模板 pipeline）
- [ ] 去掉 quality feedback（只用一次性 planning + 执行）
- [ ] 去掉 domain skills（只用通用 LLM，不加载 cryo-ET 领域知识）
- [ ] 去掉 dataset inspection（不给 agent 读取 MRC header 等数据质量信息）
- [ ] 去掉 tool availability checking
- [ ] 限制 parameter search budget（1 retry vs 3 retries vs 5 retries）

**关键分析：** 展示完整系统与每个消融版本之间的 performance gap，证明每个组件的必要性。

---

### Phase 4: Paper Writing (第 5-6 月)
**目标：完成论文初稿并迭代**

#### 4.1 论文结构
```
Title: A quality-guided large language model agent for autonomous cryo-ET data processing

1. Introduction
   - cryo-ET 数据处理的专家依赖问题
   - LLM agents 在科学计算中的新兴应用
   - 本文的贡献概述

2. Related Work
   - cryo-ET 自动化工具 (Warp, Scipion, RELION pipeline)
   - LLM for scientific discovery / code generation
   - Automated machine learning (AutoML) 的类比

3. Methods
   3.1 System Architecture
       - Workflow Planner, Executor, Quality Evaluator, Controller
   3.2 Domain Knowledge Integration
       - Skill system design
       - Parameter search space definition
   3.3 Quality Evaluation Pipeline
       - 程序化质量指标
       - 闭环决策逻辑
   3.4 Baseline Methods

4. Experiments
   4.1 Datasets
   4.2 Evaluation Protocol
   4.3 RQ1: Workflow Decision Quality
   4.4 RQ2: Parameter Selection Quality
   4.5 RQ3: Closed-Loop Optimization
   4.6 RQ4: End-to-End Reconstruction Quality
   4.7 Ablation Studies

5. Discussion
   - Agent 在哪些情况下表现好/差
   - 与人类专家的互补关系
   - Limitations
   - 未来方向：扩展到 subtomogram averaging、model building 等

6. Conclusion
```

#### 4.2 Figures & Tables Plan
- Figure 1: System architecture overview (closed-loop 示意图)
- Figure 2: 四种 pipeline 的 FSC curves (overlay, 每个数据集一个子图)
- Figure 3: RQ3 的迭代改进轨迹 (quality metric vs iteration)
- Figure 4: Ablation study 结果 (bar chart, 各组件贡献)
- Table 1: Dataset summary (sample, resolution, publication)
- Table 2: RQ1 工作流选择对比矩阵
- Table 3: 完整 metrics 对比表（所有 pipeline × 所有数据集）

---

## 三、风险管理

| 风险 | 概率 | 缓解措施 |
|------|------|----------|
| Agent FSC 无法接近专家 | 中 | 缩小 scope 到 pipeline 子集（如只做到 reconstruction）；用人工辅助的 hybrid mode |
| 工具安装/兼容性问题 | 高 | 使用 Docker/Singularity 容器化；优先选择有 conda/pip 安装的工具 |
| 数据集太大，计算成本过高 | 高 | 先做 subset（小 tomogram, 少 particle）；用 HPC 集群 |
| LLM 无法有效解释质量反馈 | 中 | 将质量反馈做得更结构化；加入人类可读的 summary |
| Reviewer 质疑 "agent 只是参数搜索" | 中 | 消融实验展示 LLM 理解的质量反馈决策 vs 随机搜索 |
| Reviewer 质疑 "FSC 不代表真实质量" | 中 | 多指标评估；FSC 标准化；manual inspection of reconstructions |
| 不同工具链不可比 | 中 | 每个 baseline 限制使用相同工具；或添加跨工具的公平性分析 |

---

## 四、时间线

```
Month 1     Month 2     Month 3     Month 4     Month 5     Month 6
[  Phase 1: Engineering Foundation  ]
            [  Phase 2: Benchmark    ]
                        [  Phase 3: Experiments & Ablation  ]
                                                    [ Phase 4: Paper  ]
              ▲                        ▲               ▲
              |                        |               |
         Prototype ready         Results complete   Draft ready
         (内部测试)                (数据分析)          (submit)
```

---

## 五、立即可以开始的工作（接下来 2 周）

### Priority 1: 技术验证（先做一个最小闭环）
选一个最简单的数据集（如 EMPIAR-10164 的一个小 tilt series），手动搭建端到端流程：
1. Raw frames → MotionCor3 → IMOD alignment → AreTomo reconstruction
2. 用硬编码参数跑通，确保所有工具可用
3. 记录每一步的输入输出和关键质量指标
**目标：证明工具链是可执行的**

### Priority 2: Quality Evaluator MVP
在 Phase 1.3 之前，先实现一个最小版本：
- 解析 IMOD alignment log，提取 residual
- 解析 CTF output，提取 max resolution
- 读取 MRC header

### Priority 3: 论文调研
- 系统搜索 cryo-ET automation 相关文献
- 搜索 LLM agent for scientific computing 相关文献
- 确认没有类似工作（避免撞车）

### Priority 4: Docker 环境搭建
- 创建包含所有 cryo-ET 工具的 Docker image
- 确保可复现性
- 这对 benchmark 和论文重现性至关重要

---

## 六、工具链推荐

| 处理步骤 | 首选工具 | 替代工具 | 备注 |
|----------|----------|----------|------|
| Motion Correction | MotionCor3 | Warp | MotionCor3 最常用，文档完善 |
| CTF Estimation | CTFFIND4 | Gctf | CTFFIND4 与 IMOD/RELION 集成好 |
| Tilt Alignment | IMOD (etomo) | AreTomo (内置) | IMOD 最标准 |
| Reconstruction | AreTomo | IMOD (tilt) | AreTomo 质量更好 |
| Particle Picking | crYOLO | RELION template matching | crYOLO 速度更快 |
| Subtomogram Averaging | RELION | Dynamo | RELION 最常用 |
| FSC Calculation | RELION (relion_postprocess) | 自定义脚本 | 标准化 mask 很重要 |

建议第一阶段固定工具链为：**MotionCor3 → CTFFIND4 → AreTomo → crYOLO → RELION**，减少变量。

---

## 七、论文投稿策略

| 期刊 | 合适度 | 策略 |
|------|--------|------|
| **Nature Methods** | 高（如果有很强的实验结果） | 需要 agent 在某些数据集上明显优于 expert |
| **Nature Computational Science** | 高 | 计算+领域交叉，比较对口 |
| **Bioinformatics** | 中高 | 如果实验结果是"接近但不超过"expert |
| **Journal of Structural Biology** | 中 | cryo-ET 领域期刊，但可能对 LLM 接受度低 |
| **ISMB/ECCB proceedings** | 中 | 可以先投会议，再扩展期刊 |

建议：先投 Nature Computational Science，如果被拒转 Bioinformatics。

---

## 八、关键成功因素

1. **闭环系统必须跑通**：这是一个 engineering challenge，也是一票否决项。如果只有 planner 没有 executor+evaluator，论文无法成立。

2. **实验必须严谨**：四种 baseline 的 FSC 计算必须完全标准化。审稿人会对 FSC comparison 极其严格。

3. **消融实验必须有力**：必须证明每个组件（domain skills, quality feedback, parameter space, tool checking）都有独立贡献。

4. **不要过度 claim**：论文应该 claim "接近专家质量 + 减少人工干预"，而不是"超越人类专家"。

5. **可复现性**：所有代码、数据、参数、provenance log 必须可以公开。Docker 环境至关重要。
