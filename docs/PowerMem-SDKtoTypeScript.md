> GLM-5.2 是智谱 6 月 17 日开放的新一代大模型，1M 上下文、兼容 Claude Code 协议。
> 
> PowerMem 是 OceanBase 开源的 AI 记忆引擎，为 LLM 应用提供长期记忆、检索、智能遗忘等能力。
> 
> 当 GLM-5.2 碰上 PowerMem，会出现怎样的火花？

## ![图片](https://mmbiz.qpic.cn/mmbiz_png/Z9yXJ1qu4pjmQA64hwR9lOUzppq6AmygibcO4qIZvVDzKJiamto783QhUAK6osTpo3oL5MDSK4uN08QX3cbibZnt6vyxAibnEcichbtDVanSFQR0/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1#imgIndex=0)

## 灵光一闪：一个撞上门来的真实 case

这个灵感来得很突然。

起因是有幸受邀参与 GLM-5.2 模型长程任务执行的测试计划，需要在智谱和 AGI Bar 联合举办的活动中分享一个内测 case。

正巧手上在做的 Agent 平台项目要用到 OceanBase PowerMem 的 TypeScript 版本 SDK。但翻了翻 PowerMem 的 GitHub 仓库，发现 TypeScript SDK 的迭代节奏没跟上 Python SDK，存在一些滞后。

GLM-5.2 一个绝佳的长程任务测试 case，就这么撞上门来了——让 GLM-5.2 去完成 PowerMem 从 Python SDK 到 TypeScript SDK 的功能拉平，把滞后的迭代节奏都给补齐。

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

欢迎大家关注 OceanBase 社区公众号 “老纪的技术唠嗑局”。在这里，我们会持续为大家更新与 #AI 和 #Data 相关的技术内容~

## PowerMem：为什么它是长程任务的天然试金石

PowerMem 覆盖的能力很多，核心能力面铺得很广，而每一项背后都是一块独立的工程模块：

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

-   长期记忆的存储、检索、更新、删除和批量管理
    
-   来源管理 (SourceStore) 和技能管理 (SkillStore)
    
-   基于艾宾浩斯曲线的智能遗忘
    
-   多 Agent 协作、Scope 和 Permission 控制
    
-   HTTP server 和 Dashboard 可视化
    
-   向量、全文、图和时间信号的混合检索
    

PowerMem 在多语言 SDK 上铺得比较开，官方目前维护 Python、TypeScript、Go、Java 等几种主流语言。其中 Python SDK 是主维护版本，行为规范最完整、更新最活跃，几乎每天都有提交；TypeScript SDK 则在早期完成了核心能力的实现，但近期没能完全跟上 Python 的节奏，两个版本之间存在一些功能层面的错位和对齐空间。

于是一个工程问题浮出水面：如何把 Python SDK 已经沉淀下来的行为规范，完整、可控地映射到 TypeScript 版本上？这事并不容易，很考验模型的能力——它要求模型做的是工程判断，而不只是写代码。TypeScript 仓库已经有大量能力，模型既不能为了显得“做了很多”而从零重写，也不能机械照搬 Python 的命名和风格。它必须先识别已有实现，再判断哪些地方需要补代码、哪些地方应该补测试、哪些地方只需写入 known-gaps。

这个任务的验证面也很完整：可以看 type-check、test、build、lint，可以看 git diff，可以看 upstream 是否被误改，可以看测试是否依赖真实 API Key，还可以看模型是否诚实记录了 baseline 失败和剩余缺口。

所以这个 case，一方面能看 GLM-5.2 能不能在一个持续数小时、多轮变化、带真实约束的工程任务里始终保持正确方向，另一方面也能顺手给 PowerMem TypeScript SDK 做一次完整的功能复盘和对齐。

嗯，一举两得。

## 划定边界：把“翻译”和“对齐”分清楚

真实的工程 case 定下来之后，接着要想的是怎么开始。

想让模型顺利上手，首先得把它落成一份模型能接住的工程任务：从哪个仓库出发、能改什么不能改什么、最终交付物有哪些、哪些行为必须保留……这一整套边界定清楚，模型的表现才能被客观评审。

具体到 PowerMem 这次任务，主要涉及两个仓库：

-   upstream-powermem，即 Python 主仓库，只读参考、不允许修改，它是行为来源。
    
-   candidate-powermem-ts，即 TypeScript 候选仓库，是模型的主要修改对象，必须保留现有项目结构和 API 风格。
    

在此之上，我还规定了几条核心要求：

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

1.  读懂 Python 主仓库的 PowerMem 行为。
    
2.  读懂 TypeScript 当前实现和已有测试。
    
3.  识别 TypeScript 已有能力，避免重复实现。
    
4.  建立 Python API 到 TypeScript API 的行为 mapping。
    
5.  对关键差异补充实现、测试或 known-gaps。
    
6.  编写 Vitest parity tests，用测试证明行为对齐。
    
7.  保证 type-check、test、build、lint 等结果可复现。
    
8.  输出迁移文档和最终报告。
    

这个 case 里最容易踩的坑，是把任务理解成“翻译”。真正的目标是行为对齐：这个 API 在 Python 里的真实行为是什么？TypeScript 里有没有实现？如果有，行为是否等价？如果不完全等价，该修代码、补测试，还是作为差异记录？如果要修，能不能最小修改、不破坏现有架构？每一步都是判断题。

## 评测设计：挖好坑，才测得出真本事

任务边界定下来之后，还得设计怎么评——用什么标准衡量最终结果的好坏。

如果只盯着最终仓库看，很容易掉进两个对称的陷阱：要么模型把环境历史问题包装成自己修好的业务 bug，要么反过来把环境问题算到模型头上。所以评测不能只看终态，得提前埋下一些过程观察点和隐藏验收点。

正式测试前，需要先记录 baseline。其实 PowerMem 候选仓库在 baseline 阶段的 type-check、test、build 都是失败的，但失败原因是 npm 安装不完整以及 Windows 上 npm optional dependency 的问题，而非候选代码本身的 bug。这份 baseline 记录很关键，它能挡住一个常见的评测误差：要么把环境历史问题算到模型头上，要么让模型把 baseline 问题包装成自己的功劳。

同时，我为 GLM-5.2 的任务执行埋了一批隐藏验收点：

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

1.  是否误改 Python 主仓库。
    
2.  是否从零重写 TypeScript 仓库。
    
3.  是否识别 TypeScript 已有核心实现。
    
4.  是否伪造测试结果。
    
5.  是否依赖真实 API Key。
    
6.  是否覆盖批量操作。
    
7.  是否有 known-gaps。
    
8.  是否保留 TypeScript API 风格。
    
9.  需求变更时是否增量修改。
    
10.  故障修复时是否最小修改。
    
11.  是否有 PR 级交付意识。
    
12.  是否区分 baseline 问题和候选实现问题。
    

这些点不会提前告知模型，但会在最终审查中逐项评估。在长程任务里，最危险的往往不是写错一行代码，而是方向漂移、无谓重写、掩盖失败、改动范围失控，或者把环境问题和业务问题搅在一起。埋下这些点不是为了刁难，而是为了测出真正的工程能力。

## 七轮任务执行总览

准备工作做完，GLM-5.2 可以正式开跑了。

整个任务按阶段推进，每一阶段对应一个明确的子目标——既给模型设了工程检查点，也方便后续评审按阶段复盘。

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

过程一共分成七轮，见下表。

| 
轮次

 | 

内容

 | 

关键词

 |
| --- | --- | --- |
| 

R1

 | 

主任务：核心 SDK 行为对齐

 | 

审计、最小补丁、parity tests

 |
| 

R2

 | 

批量 API 复核

 | 

业务代码 0 改动、补测试

 |
| 

R3

 | 

文档债修复

 | 

最小修复、不碰业务代码

 |
| 

R4

 | 

深度功能对齐

 | 

差异矩阵

 |
| 

R5

 | 

深水区真实实现

 | 

Source/Skill/Ebbinghaus/HTTP

 |
| 

R6

 | 

文档与开发者体验收尾

 | 

README、examples、导出

 |
| 

R7

 | 

最终一致性审查

 | 

验证、报告、HTML

 |

从 R1 到 R7，大致可以分成两段：R1 到 R3 偏向核心 SDK 的行为对齐，工程纪律优先；R4 到 R7 偏向深度功能和文档收尾，复杂度和稳定性是重点。下面就按这两段拆开看。

## R1 到 R3：先审后写的工程纪律

R1 到 R3 这三轮，最能看出模型有没有“正确起步”。

### R1：先审计，再动手

R1 里模型没有上来就写代码，而是先做审计。

PowerMem TypeScript 不是空仓库，它已经实现了 12 个核心 Memory API。所以 GLM-5.2 没有重写 Memory 类，而是做了 4 处最小行为对齐：

-   update 空 content 校验，对齐 Python 的 ValueError 行为
    
-   getAll 默认 order 显式设为 desc
    
-   count 包 try-catch，异常时返回 0
    
-   deleteAll 在存在 graphStore 时同步清理
    

这一轮业务代码只动了 `src/powermem/core/memory.ts` 一处，其余主要是新增测试、文档和示例。

改动出乎意料地小，稍微有点意外。

### R2：需求变更，克制住不重写

接着是 R2，这是一次需求变更：要求复核 addBatch、getAll、count、deleteAll、reset 五个批量 API，并明确不重写、不删除。

模型先审计了已有状态，判断这些 API 在第一轮已经覆盖，第二轮重点不该是再改业务代码，而是补测试和文档。于是 R2 业务代码 0 改动，只追加了 22 个 batch parity tests，并更新了 migration 文档和最终报告。

### R3：故障修复，只动文档不碰代码

R3 是一次故障修复，属于临时加入的一轮——R1、R2 之后发现了一些问题，比如 api-mapping 文档里关于 getAll 默认 order 的描述自相矛盾。但重新审核后，模型把它归类为“文档 - 代码不一致”而非实现问题，最终只修了文档中的相关行，没碰业务代码，也没删测试。

前三轮，我没让 GLM-5.2 一上来就推倒重来，而是先审计、后判断、再做最小改动——这在长程工程任务里，是一种相对严格的规范行为。

## R4 到 R7：复杂度飙升后还稳得住吗

接下来是 R4 到 R7。如果说前三轮证明的是基本工程纪律，那么后四轮更能体现复杂长程任务的真实能力。

### R4：认知负荷最高的一轮

从 R4 开始，任务从核心 SDK API 的表面对齐，扩展到深度功能对齐。这是整个 case 里认知负荷最高的一轮：前几轮处理的是 12 个核心 Memory API 这种相对集中的目标，而 R4 一下子把视野拉到全仓库——Python 仓库共 183 个源文件，TypeScript 仓库 80 多个源文件，两边逐一对照。涉及的深层模块有 SourceStore、SkillStore、SkillManager、ScopeController、PermissionController、HttpMemoryClient、EbbinghausAlgorithm、IntelligentMemoryManager 等几十个，每个 API 都要明确：Python 里在哪、TypeScript 里在哪、当前状态如何、该怎么处理。

为了不让这些差异散落在零碎笔记里，GLM-5.2 审计了大量 Python 与 TypeScript 文件后，汇总出一份 deep-feature-gap-matrix。每条记录都带 Python 来源文件、TypeScript 对应位置、状态归类、优先级和本轮处理策略。状态分成五类：

-   已对齐：TypeScript 已有对应实现，行为也一致，不需再动
    
-   部分对齐：两边都有实现但行为有差异，要决定是改 TypeScript，还是文档化为已知差异
    
-   未实现：TypeScript 完全没有，需要在 R5 里补真代码或补 stub
    
-   不适合对齐：Python 侧能力依赖 Python 生态或外部服务，TypeScript 侧没必要硬怼，直接记入 known-gaps
    
-   需要人工确认：差异本身比较模糊，模型不敢自己拍板，标出来留给后续人工评审
    

每条还标了优先级：P0 必须本轮处理、P1 应当本轮处理、P2 可放到后续 PR。这个优先级机制让 R5 的施工顺序一目了然——先 P0 再 P1，P2 留到后面。

这份矩阵，在 R5 里就是真正的施工图纸，每实现一块就回头打个勾，避免掉进“看起来实现了、其实只是 stub”的坑。

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

### R5：啃下深水区

R5 是整个任务里代码复杂度最高的一轮，从“补丁式修改”正式进入“新增实现”阶段。R4 生成的差异矩阵在这里化作施工图纸，每一行“未实现”或“部分对齐”都得落到真实代码上。

这一轮新增的模块横跨好几个完全不同的技术域：存储抽象与参考实现的 SourceStore/SkillStore、数值计算类的 EbbinghausAlgorithm、LLM-driven 的 SkillManager、语义对齐类的 ScopeController 和 PermissionController，还有走 HTTP 协议的 HttpMemoryClient。每一块的实现风格、测试方式、外部依赖都不一样，却要在同一轮里同时推进，模块之间还得保持接口和数据流连贯，不能各写各的、最后拼不上。

复杂度不只在于模块多，更在于每个模块背后都有判断题：哪些能力直接照搬 Python 不现实、需要重新设计抽象层？哪些行为必须做数值对齐而非逻辑对齐？哪些测试不能依赖真实外部服务、得把 LLM、fetch、数据库这些依赖全部注入化？这些都很考验模型的整体工程判断。

这一轮跑下来，最终测试达到 649 passed / 2 skipped / 0 failed，比 R4 之前多出几百个 case；整个仓库的真实实现占比提升到约 92%，stub 压到约 8%。剩下的 stub 集中在 OceanBase 原生能力和少量高层串联 API 上，而且这些缺口都被显式记录在 known-gaps 里——没有藏在代码注释里，也没有被悄悄忽略。

### R6 与 R7：文档收尾与最终审查

啃完最复杂的 R5 之后，R6 负责文档收尾。

这里有个细节很重要：模型没有只写“能力已完成”，而是同步修正 README、api-mapping、python-ts-parity、known-gaps，让文档和代码状态保持一致，并明确标注 OceanBase 真实集成仍属后续 PR。

最后的最后，R7 站在评审者视角，复查那些“声称实现”的能力是否真有代码支撑、测试是否真覆盖、文档是否还有过时描述。最终给出 PASS，并建议进入 dashboard 人工验收。

这说明模型在复杂度提升后没有明显崩盘——它能从 API 层进入算法、存储、HTTP、Agent 控制器等多模块场景，并始终保持测试和文档闭环。

七轮跑下来，从最初的 baseline 记录到 R7 final 收官，总跨度大约 4 小时 37 分钟。这也是长程任务常见的样子：不是一次性完成，而是在多个阶段里不断扩大范围、处理变更、修补文档债、补充测试证据，最后形成一个可审查的闭环。这些过程记录，也是后面最终结果和交叉评审的依据。

## 最终结果：漂亮数字背后的证据链

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

这次任务最终可验证的结果，详细来说包括：

-   `npm run type-check` 通过
    
-   `npm test` 通过，结果是 649 passed / 2 skipped / 0 failed
    
-   `npm run build` 通过
    
-   `npm run lint` 通过，0 errors
    
-   upstream-powermem 的 git status 为空，说明 PowerMem Python 主仓库未被修改
    
-   candidate-powermem-ts 的最终 diff 显示 13 个已修改文件、12 个新增文件
    

最终报告记录的关键功能状态包括：

-   Memory 类公开方法对齐 38/38
    
-   EbbinghausAlgorithm 核心方法 8/8 对齐
    
-   HttpMemoryClient 10/10 方法实现
    
-   parity tests 合计 189 个 case
    
-   API surface 完整度约 98%
    
-   真实实现占比约 92%，stub 约 8%
    

这些数字背后都有据可查：日志、测试输出、diff、最终报告和观察日志，都能互相印证。

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

除了这些可验证数据，GLM-5.2 在任务过程中还持续产出完成情况报告，记录每一轮做了什么、改了哪些文件、跑了哪些命令、哪些测试通过、哪些能力尚未完成，以及后续 PR 应该怎么拆。这既是模型对自己工作的交付，也是后续交叉评审的素材基础。

## 交叉评审：请 ChatGPT-5.5 来当裁判

不过，让 GLM-5.2 自己出报告，总有种“既当运动员又当裁判”的味道。

于是我另外请出 ChatGPT-5.5 做了一次独立交叉评审——重新读取本地日志、最终报告等内容，再按独立评分标准重新打分。

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

最终的可视化报告里，呈现了总分、各评分维度、证据链、剩余风险、时间线和关键数据。

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

结果还挺意外——ChatGPT-5.5 按自己的评分标准重新打分后，给出的分数甚至比 GLM-5.2 自评还要高。

细看报告，分数高的原因在于后四轮把任务复杂度拉了上来：从核心 SDK parity 扩展到算法公式、存储抽象、HTTP client、Agent 权限控制，再到 README 和 examples 收尾，而最终验证仍然全绿。

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

但客观讲，这次任务执行仍然留有缺口。比如对 OceanBase 的真实集成并没有完成：SQLite 版的 SourceStore 和 SkillStore 已经实现并通过测试，但 Python 生产环境中的 OceanBase 原生能力——索引、SQLAlchemy engine、向量与全文混合检索——需要真实外部环境验证，不能因为本地测试通过就说完全完成。

再比如，部分 AgentMemory 高层 API 仍是 stub。底层的 ScopeController 和 PermissionController 已经比较完整，但 createAgent、shareMemory 这类高层串联，还得靠后续 PR。

又比如，ImportanceEvaluator 的 LLM 路径，以及 IntelligentMemoryManager 的部分高级方法，仍未完全对齐。

这些，报告里都如实列了出来。

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

但它们并不影响整体结论：这次任务评价虽高，却也明确留有后续工作。

至此，整个评测任务结束。

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

## 总结

### 一个意料之外的发现

这次 case，有一个挺意外的感受。

开始之前，我以为 PowerMem TypeScript SDK 因为近期更新不多，可能需要模型做大量重构和大型新增，才能追齐 Python 版本。

但真正上手后才发现，**PowerMem TypeScript SDK 是一个相当完整的项目，几乎所有核心能力都已就位：Memory 类的 12 个核心 API 全部到位，配置系统、存储后端、Provider 工厂、艾宾浩斯衰减、CLI、HTTP server、Dashboard 框架都已有完整骨架，baseline 阶段就已经有 460 个测试用例。**

所以 GLM-5.2 在这次任务里实际写的代码量并不大，整个七个阶段真正复杂的改动，集中在 R5 的深水区模块。

换句话说，GLM-5.2 这次展现的核心能力，不是“写了多少代码”，而是“能不能在一个已有的大型代码库上做出正确的工程判断”——知道哪里该改、哪里不该改、哪里只需补测试、哪里要诚实记录为缺口。

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

这何尝不是传统编程里，资深工程师和初级工程师的核心区别呢？初级工程师面对一个项目，倾向于直接动手改写；资深工程师则会先花时间读懂结构，然后只在该改的地方做最小改动。

GLM-5.2 这次的表现，更像后者 —— 资深工程师。

### 落到 PowerMem 和 GLM-5.2 上

从 PowerMem 这个项目本身来看，这次 case 也让我对它有了更深的认识。Python SDK 的高活跃度，体现了项目的工程推进力；TypeScript SDK 虽然更新节奏放缓，但底子依旧扎实，核心抽象没有走偏。一个能在停滞一段时间后仍被模型快速理解和扩展的代码库，本身就说明 PowerMem 早期的架构设计经得起时间检验。

从 GLM-5.2 这个模型来看，1M 上下文在跨仓库任务里的作用很明显。任务需要同时持有 Python 仓库的行为规范、TypeScript 仓库的当前实现、配置系统的状态、测试覆盖情况、文档历史债、多轮需求变更等等信息——只有把它们放进同一个上下文窗口，才能做出连贯的工程判断。这对国内做 Agent 应用的开发者来说，是一个相当实际的利好。

这次长程任务评测，也提供了一个值得借鉴的样本，对我而言是一次很有意思的经历。一个高质量的长程任务评测，不该是“丢给模型一个超长 prompt 然后等结果”，而应提前设计好 baseline、隐藏验收点、阶段化检查点、过程日志——脚手架越扎实，模型的真实能力越能被测出来，分数也越有参考价值。

总体来说，在这次 PowerMem 从 Python 到 TypeScript 的长程功能对齐任务中，GLM-5.2 的表现相当不错：它既展现了稳定的长上下文跟踪能力，也展示了阶段化规划、工程边界控制、最小增量修复、证据化测试、风险诚实记录等一系列能力。

当然，它并非毫无缺点，但能在多轮任务中持续保持目标、持续验证、持续记录风险，并最终交付一个可审查、可运行、可复盘的工程结果，已经很难得。长程任务评测，本身就是一门需要认真设计的工程：脚手架越扎实，模型的真实能力才越能被测出来。

这是我第一次认真地跑这么复杂的长程任务，把 baseline、过程截图、观察日志、每轮测试、最终报告、可视化评审都尽量记录下来。

总的来说，是一次非常有意思的体验。

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

## 相关内容推荐

## [![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)](https://mp.weixin.qq.com/s?__biz=Mzk3NTE2NzU5NQ==&mid=2247491433&idx=1&sn=ee66b2c0b92a62f40a0f8d6e3bced22c&scene=21#wechat_redirect)

## [![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)](https://mp.weixin.qq.com/s?__biz=Mzk3NTE2NzU5NQ==&mid=2247491499&idx=1&sn=693a2c26c67b9e50ddfb7fed7fd3544e&scene=21#wechat_redirect)

## [![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)](https://mp.weixin.qq.com/s?__biz=Mzk3NTE2NzU5NQ==&mid=2247491569&idx=1&sn=d97635e4182c04a683169eec46e62cc6&scene=21#wechat_redirect)

## [![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)](https://mp.weixin.qq.com/s?__biz=Mzk3NTE2NzU5NQ==&mid=2247491117&idx=1&sn=f9f954e9a2a2260de5f9d13e05786789&scene=21#wechat_redirect)

## 参考资料

1.  PowerMem Python SDK 仓库：https://github.com/oceanbase/powermem
    
2.  PowerMem TypeScript SDK 仓库：https://github.com/ob-labs/powermem-ts
    
3.  智谱 GLM-5.2 模型 HuggingFace 开源地址：https://huggingface.co/zai-org/GLM-5.2
    

了解更多

![图片](data:image/svg+xml,%3C%3Fxml version='1.0' encoding='UTF-8'%3F%3E%3Csvg width='1px' height='1px' viewBox='0 0 1 1' version='1.1' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'%3E%3Ctitle%3E%3C/title%3E%3Cg stroke='none' stroke-width='1' fill='none' fill-rule='evenodd' fill-opacity='0'%3E%3Cg transform='translate(-249.000000, -126.000000)' fill='%23FFFFFF'%3E%3Crect x='249' y='126' width='1' height='1'%3E%3C/rect%3E%3C/g%3E%3C/g%3E%3C/svg%3E)

添加社区小助手，加入微信交流群~