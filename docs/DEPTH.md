# 深度登记 产线停机裁决与效率重算

- 规模：中型
- 核心规则：班次按休息与停机所有端点切片，先扣休息并集，再按安全、故障、换型优先级分配停机。停机原因分扣减与影响两种口径：扣减按主因互斥、合计等于停机分钟且只扣一次；影响按各原因自身区间并集，可重叠、合计可大于停机分钟，仅用于复盘。两者由同一次切片产出，停机裁决页与效率结果采用同一归属。OEE使用未舍入的三因子计算，并保留超产异常。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 班报采信 | 导入班报并保留物理行号 | `GET /api/intake` | `app/modules/m1_intake/service.py` `app/modules/m1_intake/rules.py` | `tests/test_intake.py` |
| M2 班次契约 | 规范数量、节拍与偏移时间 | `GET /api/contract` | `app/modules/m2_contract/service.py` `app/modules/m2_contract/rules.py` | `tests/test_contract.py` |
| M3 停机裁决 | 裁剪并合并重叠区间 | `GET /api/model` | `app/modules/m3_model/service.py` `app/modules/m3_model/rules.py` | `tests/test_model.py` |
| M4 效率重算 | 复算三项效率及OEE | `GET /api/calculate` | `app/modules/m4_calculate/service.py` `app/modules/m4_calculate/rules.py` | `tests/test_calculate.py` |
| M5 缺陷隔离 | 按原因筛查异常班报 | `GET /api/quarantine` | `app/modules/m5_quarantine/service.py` `app/modules/m5_quarantine/rules.py` | `tests/test_quarantine.py` |
| M6 班次对账 | 核查时间与产量守恒 | `GET /api/reconcile` | `app/modules/m6_reconcile/service.py` `app/modules/m6_reconcile/rules.py` | `tests/test_reconcile.py` |
| M7 运行复核 | 保存运行与版本复核 | `GET /api/batches` | `app/modules/m7_batches/service.py` `app/modules/m7_batches/rules.py` | `tests/test_batches.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现会怎样 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 历史编码 | 静默误算或覆盖证据 | UTF8与GB18030回退 | `app/modules/m1_intake/rules.py` | `tests/test_intake.py::test_encoding` |
| TRAP-02 | 表头BOM | 静默误算或覆盖证据 | 签名剥离 | `app/modules/m1_intake/rules.py` | `tests/test_intake.py::test_bom` |
| TRAP-06 | 全角数量 | 静默误算或覆盖证据 | NFKC后Decimal | `app/modules/m2_contract/rules.py` | `tests/test_contract.py::test_fullwidth` |
| TRAP-07 | 缺少产量 | 静默误算或覆盖证据 | 哨兵隔离 | `app/modules/m2_contract/rules.py` | `tests/test_contract.py::test_sentinel` |
| TRAP-10 | 效率精度 | 静默误算或覆盖证据 | Decimal计算不逐项舍入 | `app/modules/m4_calculate/rules.py` | `tests/test_calculate.py::test_oee` |
| TRAP-11 | 时间偏移混用 | 静默误算或覆盖证据 | 统一UTC后运算 | `app/modules/m2_contract/rules.py` | `tests/test_contract.py::test_timezone` |
| TRAP-14 | 重复班报异值 | 静默误算或覆盖证据 | 全部冲突隔离 | `app/modules/m2_contract/rules.py` | `tests/test_contract.py::test_conflict` |
| TRAP-19 | 停机多因重叠 | 静默误算或覆盖证据 | 主因互斥扣减，另记各原因影响并集；两者由同一次切片产出 | `app/modules/m3_model/rules.py` | `tests/test_model.py::test_priority` `tests/test_model.py::test_impact_keeps_each_cause` |
| TRAP-23 | 相邻区间边界 | 静默误算或覆盖证据 | 半开片段不重计 | `app/modules/m3_model/rules.py` | `tests/test_model.py::test_half_open` |
| TRAP-26 | 旧版复核 | 静默误算或覆盖证据 | 修订号条件更新 | `app/modules/m7_batches/rules.py` | `tests/test_batches.py::test_stale` |

## 对账规则
计划分钟=运行分钟+有效停机分钟。班次总分钟=计划分钟+休息并集分钟。总产=良品+废品。起止时间使用含偏移的ISO格式，班次最长24小时。区间采用[start,end)，超出班次的停机裁剪，重叠休息只扣一次。total与good为整数件，ideal_seconds为每件理想秒数。零计划、零运行、零产量分别给出状态，不以任意分母补零。停机原因的扣减口径互斥且合计等于停机分钟；影响口径按各原因区间并集可重叠，仅用于复盘，不进入OEE。

## 已知不覆盖
不推断缺失班报，不接入PLC。样例按班次隔离计算，不自动分割换产品后的节拍；混产品需分别生成班报。
