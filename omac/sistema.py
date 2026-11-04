"""Coisas que dependem do sistema operacional."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WEBVIEW2_DOWNLOAD = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
_WEBVIEW2_ID = r"{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def recurso(relativo: str) -> Path:
    """Caminho de um arquivo empacotado (funciona no .exe do PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relativo


def abrir(caminho: str | Path) -> None:
    """Abre um arquivo ou pasta no programa padrão do sistema."""
    caminho = str(caminho)
    if sys.platform == "win32":
        os.startfile(caminho)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", caminho])
    else:
        subprocess.Popen(["xdg-open", caminho])


def mostrar_na_pasta(caminho: str | Path) -> None:
    caminho = Path(caminho)
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(caminho)])
    else:
        abrir(caminho.parent)


def memoria_gb() -> float | None:
    if sys.platform == "win32":
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullTotalPhys / 1024**3
        return None
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    except (ValueError, OSError, AttributeError):
        return None


def pc_modesto() -> bool:
    """PC com pouca memória ou poucos núcleos: melhor usar o visual otimizado."""
    mem = memoria_gb()
    return (os.cpu_count() or 1) <= 2 or (mem is not None and mem < 6)


def webview2_instalado() -> bool:
    """O OMAC desenha a tela com o WebView2 (o motor do Edge) no Windows."""
    if sys.platform != "win32":
        return True
    import winreg

    locais = [
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_ID}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_ID}"),
        (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_ID}"),
    ]
    for raiz, chave in locais:
        try:
            with winreg.OpenKey(raiz, chave) as k:
                versao, _ = winreg.QueryValueEx(k, "pv")
                if versao and versao != "0.0.0.0":
                    return True
        except OSError:
            continue
    return False


def avisar_sem_webview2() -> None:
    import ctypes
    import webbrowser

    msg = (
        "Para abrir o OMAC é preciso o “Microsoft Edge WebView2 Runtime”, "
        "que é gratuito e da própria Microsoft.\n\n"
        "Clique em OK para abrir a página de download. Depois de instalar, abra o OMAC de novo."
    )
    MB_OKCANCEL, MB_ICONINFORMATION, IDOK = 0x1, 0x40, 1
    if ctypes.windll.user32.MessageBoxW(0, msg, "OMAC", MB_OKCANCEL | MB_ICONINFORMATION) == IDOK:
        webbrowser.open(WEBVIEW2_DOWNLOAD)
