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


def abrir_link(url: str) -> None:
    """Abre um link. Levanta OSError se ninguém no sistema souber abrir o endereço."""
    if url.startswith("whatsapp:"):
        if sys.platform != "win32":
            raise OSError("aplicativo do WhatsApp só no Windows")
        os.startfile(url)  # noqa: S606
        return
    import webbrowser

    if not webbrowser.open(url):
        raise OSError("nenhum navegador disponível")


def copiar_arquivo(caminho: str | Path) -> bool:
    """Põe o arquivo na área de transferência, como o Ctrl+C do Explorador."""
    if sys.platform != "win32":
        return False
    # O caminho vai pelo ambiente para não precisar escapar aspas no comando.
    try:
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Set-Clipboard -LiteralPath $env:OMAC_ARQUIVO"],
            env={**os.environ, "OMAC_ARQUIVO": str(caminho)},
            creationflags=subprocess.CREATE_NO_WINDOW,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return False  # quem chamou mostra o arquivo na pasta
    return resultado.returncode == 0


_CHAVE_INICIO = r"Software\Microsoft\Windows\CurrentVersion\Run"


def inicio_automatico_disponivel() -> bool:
    """Só o .exe no Windows: rodando pelo Python não há um programa para registrar."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def _comando_de_inicio() -> str:
    return f'"{sys.executable}"'


def inicio_automatico_ligado(nome: str = "OMAC") -> str:
    """O comando registrado para abrir com o Windows, ou "" se não houver."""
    if sys.platform != "win32":
        return ""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CHAVE_INICIO) as k:
            return winreg.QueryValueEx(k, nome)[0]
    except OSError:
        return ""


def definir_inicio_automatico(ligar: bool, nome: str = "OMAC", comando: str | None = None) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CHAVE_INICIO, 0, winreg.KEY_SET_VALUE) as k:
        if ligar:
            winreg.SetValueEx(k, nome, 0, winreg.REG_SZ, comando or _comando_de_inicio())
        else:
            try:
                winreg.DeleteValue(k, nome)
            except FileNotFoundError:
                pass


def corrigir_inicio_automatico() -> None:
    """Se o .exe mudou de lugar ou de nome, atualiza o registro para não ficar quebrado."""
    if not inicio_automatico_disponivel():
        return
    registrado = inicio_automatico_ligado()
    if registrado and registrado != _comando_de_inicio():
        definir_inicio_automatico(True)


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
