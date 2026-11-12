"""
Transcreve todos os áudios de uma pasta usando Whisper local (faster-whisper).

Uso:
    python transcrever.py

O script pergunta no terminal a pasta, o modelo, o idioma e o dispositivo a usar.
"""

import os
import sys
import time
from pathlib import Path


def registrar_dlls_cuda():
    """No Windows, adiciona as DLLs da NVIDIA (instaladas via pip) ao PATH do processo.

    O ctranslate2 carrega as DLLs da CUDA via busca no PATH, não via
    os.add_dll_directory, então é isso que precisa ser ajustado aqui.
    """
    if sys.platform != "win32":
        return
    pastas_bin = []
    for pacote in ("nvidia.cuda_runtime", "nvidia.cublas", "nvidia.cudnn"):
        try:
            modulo = __import__(pacote, fromlist=["_"])
        except ImportError:
            continue
        for caminho in getattr(modulo, "__path__", []):
            bin_dir = Path(caminho) / "bin"
            if bin_dir.is_dir():
                pastas_bin.append(str(bin_dir))
    if pastas_bin:
        os.environ["PATH"] = os.pathsep.join(pastas_bin) + os.pathsep + os.environ.get("PATH", "")

EXTENSOES_VALIDAS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma", ".opus", ".mp4"}
MODELOS_VALIDOS = {"tiny", "base", "small", "medium", "large-v3"}
DEVICES_VALIDOS = {"cpu", "cuda", "auto"}


def perguntar(mensagem: str, padrao: str) -> str:
    resposta = input(f"{mensagem} [{padrao}]: ").strip().lstrip("﻿")
    return resposta if resposta else padrao


def perguntar_opcao(mensagem: str, opcoes: set[str], padrao: str) -> str:
    while True:
        resposta = perguntar(mensagem, padrao).lower()
        if resposta in opcoes:
            return resposta
        print(f"  Opção inválida. Escolha entre: {', '.join(sorted(opcoes))}")


def coletar_especificacoes() -> dict:
    print("=== Transcrição de áudio (Whisper local) ===\n")

    pasta = perguntar("Pasta com os áudios", ".")

    modelo = perguntar_opcao(
        f"Modelo ({', '.join(sorted(MODELOS_VALIDOS))})", MODELOS_VALIDOS, "small"
    )

    idioma = perguntar("Idioma do áudio (ex: pt, en, ou vazio para detectar automaticamente)", "")
    idioma = idioma or None

    device = perguntar_opcao(f"Dispositivo ({', '.join(sorted(DEVICES_VALIDOS))})", DEVICES_VALIDOS, "cpu")

    saida = perguntar("Pasta para salvar as transcrições (vazio = mesma pasta dos áudios)", "")
    saida = saida or None

    print()
    return {"pasta": pasta, "modelo": modelo, "idioma": idioma, "device": device, "saida": saida}


def encontrar_audios(pasta: Path) -> list[Path]:
    return sorted(
        p for p in pasta.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSOES_VALIDAS
    )


def formatar_timestamp(segundos: float) -> str:
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = segundos % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def transcrever_arquivo(model, caminho: Path, idioma: str | None) -> tuple[str, list]:
    segments, info = model.transcribe(str(caminho), language=idioma, vad_filter=True)
    segmentos = list(segments)
    texto = " ".join(seg.text.strip() for seg in segmentos)
    return texto, segmentos, info


def main():
    spec = coletar_especificacoes()

    pasta = Path(spec["pasta"]).expanduser().resolve()
    if not pasta.is_dir():
        print(f"Erro: pasta não encontrada: {pasta}")
        sys.exit(1)

    audios = encontrar_audios(pasta)
    if not audios:
        print(f"Nenhum arquivo de áudio encontrado em: {pasta}")
        print(f"Extensões suportadas: {', '.join(sorted(EXTENSOES_VALIDAS))}")
        sys.exit(0)

    pasta_saida = Path(spec["saida"]).expanduser().resolve() if spec["saida"] else pasta
    pasta_saida.mkdir(parents=True, exist_ok=True)

    print(f"Encontrados {len(audios)} arquivo(s) de áudio em: {pasta}")
    print(f"Carregando modelo Whisper '{spec['modelo']}' (device={spec['device']})...")

    registrar_dlls_cuda()
    from faster_whisper import WhisperModel

    device = spec["device"]
    try:
        model = WhisperModel(spec["modelo"], device=device, compute_type="int8")
    except Exception as e:
        if device != "cpu":
            print(f"Falha ao usar device='{device}' ({e}). Usando CPU.")
            model = WhisperModel(spec["modelo"], device="cpu", compute_type="int8")
        else:
            raise

    for i, audio in enumerate(audios, start=1):
        destino = pasta_saida / f"{audio.stem}.txt"
        if destino.exists():
            print(f"[{i}/{len(audios)}] {audio.name} -> já transcrito, pulando ({destino.name})")
            continue

        print(f"[{i}/{len(audios)}] Transcrevendo {audio.name}...")
        inicio = time.time()
        try:
            texto, segmentos, info = transcrever_arquivo(model, audio, spec["idioma"])
        except Exception as e:
            if device != "cpu":
                print(f"  Falha na GPU ao transcrever ({e}). Trocando para CPU e tentando de novo...")
                device = "cpu"
                model = WhisperModel(spec["modelo"], device="cpu", compute_type="int8")
                try:
                    texto, segmentos, info = transcrever_arquivo(model, audio, spec["idioma"])
                except Exception as e2:
                    print(f"  Erro ao transcrever {audio.name}: {e2}")
                    continue
            else:
                print(f"  Erro ao transcrever {audio.name}: {e}")
                continue
        duracao = time.time() - inicio

        with open(destino, "w", encoding="utf-8") as f:
            f.write(texto.strip() + "\n")

        destino_com_tempo = pasta_saida / f"{audio.stem}.timestamps.txt"
        with open(destino_com_tempo, "w", encoding="utf-8") as f:
            for seg in segmentos:
                inicio_t = formatar_timestamp(seg.start)
                fim_t = formatar_timestamp(seg.end)
                f.write(f"[{inicio_t} -> {fim_t}] {seg.text.strip()}\n")

        print(f"  Idioma detectado: {info.language} (confiança: {info.language_probability:.0%})")
        print(f"  Concluído em {duracao:.1f}s -> {destino.name}")

    print("\nTranscrição finalizada.")


if __name__ == "__main__":
    main()
