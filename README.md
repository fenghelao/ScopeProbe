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
| `scope_measure_dc(channel, vdiv_mv, samples, samplerate)` | 采通道 → 算 **DC 电压**(中位码值→电压);`vdiv_mv=0` 自动切档(1V/2V/5V per div),带 `tried`/`clipping`/`hint` |
| `scope_capture_stats(channel, ...)` | 采波形返回码值统计(min/max/mean/median/峰峰),快速看信号在不在/抖不抖 |

## DC 电压换算

DSCope 8-bit 码值随电压**反向**(code 越小电压越高):

```
V = (hw_offset - code) * (vdiv_mv * vfactor * 10) / (ref_max - ref_min) / 1000
```

标定常数(`vdiv_mv/hw_offset/ref_min/ref_max`)从 `wavegate-capture acquire` 输出读,**vdiv 跟随 DSCope 当前档位**。1V/div 时量程约 ±5V。

### 自动切档量程

`scope_measure_dc(channel, vdiv_mv=0, ...)`:
- `vdiv_mv=0`（默认）→ **自动切档**:依次试 1V/2V/5V per div，取不贴量程边界（`ref_min/ref_max ±2`）的那档。量 ~12V 输入会自动切到 2V/div。
- `vdiv_mv>0` → 固定该档（mV/div）。
- 返回带 `tried`（各档尝试）、`clipping`、`hint`。

> **依赖 `wavegate-capture` 支持 `--vdiv`**（本仓库配套的 WaveGate 已加该参数）。若用的是旧版 `wavegate-capture`（不认 `--vdiv`），它会忽略该参数、维持设备当前档位，自动切档退化为"检测+提示"，此时 >±5V 需在 DSView 手动调大 vdiv。

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
