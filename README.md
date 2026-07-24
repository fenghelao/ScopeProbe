# ScopeProbe MCP

让 AI 经 **MCP** 读 **DreamSourceLab DSCope**(如 DSCope U3P100)的电压/波形——用于数字电源等硬件的**在线自测与采样校准**。

配合配套的 **MultiProbeFlash MCP**(烧录/SWD/RTT/串口)成套:一个管**烧录+调试**,一个管**示波器测量**,AI 可闭环「改码→编译→烧录→RTT/串口验证→示波器量电压」。

## 为什么单独做

- mainline `sigrok-cli` **不支持 DSCope**(需 DreamSourceLab 分叉的 `libsigrok4DSL`)。
- 现成 scope MCP 都不覆盖 DSCope:
  - [KenosInc/sigrok-mcp-server](https://github.com/KenosInc/sigrok-mcp-server)(Go,包 sigrok-cli,偏逻辑分析/协议解码)
  - [MagnusJohansson/siglent-sds-mcp](https://github.com/magnusjohansson/siglent-sds-mcp)、[lxkang00/oscilloscope-mcp](https://glama.ai/mcp/servers/lxkang00/oscilloscope-mcp)(Python,SCPI 网口控 Siglent)
  - Rigol DHO / Digilent WaveForms 等
- 本 server 直接包 WaveGate 的原生采集器 `wavegate-capture`(sigrok4dsl 后端,已驱动 DSCope),把测量暴露成 MCP。

## 工具

| 工具 | 说明 |
|---|---|
| `scope_scan` | 扫描 DSCope 设备(model/serial/通道) |
| `scope_measure_dc(channel, samples, samplerate)` | 采通道 → 算 **DC 电压**(中位码值→电压);带 `clipping`/`hint` 自适应量程提示 |
| `scope_capture_stats(channel, ...)` | 采波形返回码值统计(min/max/mean/median/峰峰),快速看信号在不在/抖不抖 |

## DC 电压换算

DSCope 8-bit 码值随电压**反向**(code 越小电压越高):

```
V = (hw_offset - code) * (vdiv_mv * vfactor * 10) / (ref_max - ref_min) / 1000
```

标定常数(`vdiv_mv/hw_offset/ref_min/ref_max`)从 `wavegate-capture acquire` 输出读,**vdiv 跟随 DSCope 当前档位**。1V/div 时量程约 ±5V。

### 自适应量程

`scope_measure_dc` 检测码值是否贴近量程边界(`ref_min/ref_max ±2`):贴边 → `clipping=True` + 提示。
量 >±5V(如 12V 输入)需把该通道 vdiv 调到 2V/div 以上——**当前 wavegate-capture 跟随设备档位,vdiv 在 DSView 里设**。
> 路线图:给 `wavegate-capture` 加 `--vdiv` 让 MCP 全自动切档(现为半自动:检测+提示)。

## 依赖 & 配置

- `pip install mcp`
- `wavegate-capture.exe`(sigrok4dsl 后端);路径经环境变量 `WAVEGATE_CAPTURE` 指定。
- DSCope USB 接入;**同一时刻别和 DSView / WaveGate GUI 抢设备**。

Claude Code `.mcp.json`:

```json
{ "mcpServers": { "scopeprobe": {
  "command": "uv",
  "args": ["run","--with","mcp","python","scopeprobe_mcp.py"],
  "env": { "WAVEGATE_CAPTURE": "C:/.../wavegate-capture.exe" }
} } }
```

## 实测

- DSCope CH0 接数字电源输出(5V):`scope_measure_dc(0)` → **5.02V**;固件读 4.99V,吻合 ~0.6%。
- 12V 输入侧:1V/div 超量程(`clipping=True`)→ 提示调 2V/div。

## 开发约定

沿用配套 MultiProbeFlash 的「功能必进 MCP」：新增采集/测量能力都在此暴露对应 MCP 工具。

## License

MIT —— 见 [LICENSE](LICENSE)。
