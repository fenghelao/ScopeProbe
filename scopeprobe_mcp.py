#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ScopeProbe MCP —— 让 AI 经 MCP 读 DreamSourceLab DSCope 的电压/波形。

为什么单独做:mainline sigrok-cli 不支持 DSCope(需 DreamSourceLab 的 libsigrok4DSL 分叉),
现成的 scope MCP(Siglent/Rigol SCPI、Digilent WaveForms、KenosInc/sigrok-mcp-server)都不覆盖 DSCope。
本 server 直接包 WaveGate 的原生采集器 `wavegate-capture`(sigrok4dsl 后端,已驱动 DSCope U3P100),
把「扫描 / 测直流电压 / 采波形统计」暴露成 MCP 工具,配合数字电源等硬件调试/自测。

依赖:
  · wavegate-capture.exe(sigrok4dsl 后端)。路径经环境变量 WAVEGATE_CAPTURE 指定,
    默认取 WaveGate 仓库的 build-sigrok/Release/wavegate-capture.exe。
  · DSCope 通过 USB 接入;同一时刻只有一个进程能占它(别和 DSView/WaveGate GUI 同时用)。

DC 电压换算(源自 wavegate-capture 的标定):
  V = (hw_offset - code) * (vdiv_mv * vfactor * DSO_VDIVS) / (ref_max - ref_min) / 1000
  DSCope 码值随电压反向(code 越小电压越高);标定常数从 acquire 输出里读,vdiv 跟随设备当前档位。
"""
import os
import json
import subprocess
import statistics
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("scopeprobe")

_DEFAULT_CAP = r"C:\Users\Administrator\.agit_lab\WaveGate\native\wavegate-capture\build-sigrok\Release\wavegate-capture.exe"
CAP = os.environ.get("WAVEGATE_CAPTURE", _DEFAULT_CAP)
DSO_VDIVS = 10.0          # DSCope 竖向格数(满量程 = vdiv * 10)


def _run(args, timeout=45):
    p = subprocess.run([CAP] + args, capture_output=True, text=True, timeout=timeout)
    for ln in reversed(p.stdout.splitlines()):        # 最后一行 JSON
        ln = ln.strip()
        if ln.startswith("{"):
            return json.loads(ln)
    raise RuntimeError("wavegate-capture 无 JSON 输出: %s" % p.stdout[-200:])


def _code_to_voltage(code, cal):
    fs_mv = cal["vdiv_mv"] * cal.get("vfactor", 1.0) * DSO_VDIVS
    span = cal["ref_max"] - cal["ref_min"]
    if span <= 0:
        return 0.0
    return (cal["hw_offset"] - code) * fs_mv / span / 1000.0


@mcp.tool()
def scope_scan() -> dict:
    """扫描 DSCope 设备。返回 {ok, devices:[{model,serial,channels,...}]}。"""
    try:
        return _run(["scan", "--backend", "sigrok4dsl"], timeout=30)
    except Exception as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
def scope_measure_dc(channel: int = 0, samples: int = 20000, samplerate: int = 10000000) -> dict:
    """采 DSCope 通道 channel,算 **DC 电压**(中位码值→电压)。
    返回 {ok, voltage, code_median, code_min, code_max, vdiv_mv, clipping, hint}。
    自适应:若码值贴近量程边界(ref_min/ref_max ±2),clipping=True,hint 提示在 DSView 调大 vdiv
    (如 1V/div 量程约 ±5V,量 12V 需调到 2V/div 以上;wavegate-capture 跟随设备当前 vdiv 档位)。"""
    try:
        j = _run(["acquire", "--backend", "sigrok4dsl", "--test-channels", "ch%d" % channel,
                  "--channel", str(channel), "--mode", "single",
                  "--samplerate", str(samplerate), "--samples", str(samples)])
    except Exception as e:
        return {"ok": False, "error": str(e)}
    try:
        cm = j["record"]["channelMetrics"]["ch%d" % channel]
        cal = {"vdiv_mv": cm["voltageVdivMv"], "hw_offset": cm["voltageHwOffset"],
               "ref_min": cm["voltageRefMin"], "ref_max": cm["voltageRefMax"], "vfactor": 1.0}
        codes = j.get("waveform") or j.get("waveforms", {}).get("ch%d" % channel) or []
        if not codes:
            return {"ok": False, "error": "无波形样本", "raw_metrics": cm}
        med = statistics.median(codes)
        clip = (med <= cal["ref_min"] + 2) or (med >= cal["ref_max"] - 2)
        return {"ok": True,
                "voltage": round(_code_to_voltage(med, cal), 3),
                "code_median": med, "code_min": min(codes), "code_max": max(codes),
                "vdiv_mv": cal["vdiv_mv"], "clipping": clip,
                "hint": ("信号贴量程边界，可能超量程——在 DSView 把该通道 vdiv 调大(量 >±5V 用 2V/div+)" if clip else "")}
    except Exception as e:
        return {"ok": False, "error": "解析失败: %s" % e}


@mcp.tool()
def scope_capture_stats(channel: int = 0, samples: int = 20000, samplerate: int = 10000000) -> dict:
    """采一段波形返回码值统计(min/max/mean/median/峰峰码),不做电压换算——快速看信号在不在、抖不抖。"""
    try:
        j = _run(["acquire", "--backend", "sigrok4dsl", "--test-channels", "ch%d" % channel,
                  "--channel", str(channel), "--mode", "single",
                  "--samplerate", str(samplerate), "--samples", str(samples)])
        codes = j.get("waveform") or j.get("waveforms", {}).get("ch%d" % channel) or []
        if not codes:
            return {"ok": False, "error": "无波形样本"}
        return {"ok": True, "n": len(codes), "code_min": min(codes), "code_max": max(codes),
                "code_mean": round(sum(codes) / len(codes), 2), "code_median": statistics.median(codes),
                "code_pp": max(codes) - min(codes)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()
