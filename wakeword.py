"""ウェイクワード検知（「ジャービス」と呼ばれるまで待つ）"""
import numpy as np
import sounddevice as sd

import config


class WakeWordDetector:
    def __init__(self):
        engine = config.WAKEWORD_ENGINE
        if engine == "auto":
            engine = "porcupine" if config.PICOVOICE_ACCESS_KEY else "openwakeword"
        self.engine = engine

        if engine == "porcupine":
            import pvporcupine

            self._porcupine = pvporcupine.create(
                access_key=config.PICOVOICE_ACCESS_KEY,
                keywords=["jarvis"],
                sensitivities=[config.WAKEWORD_SENSITIVITY],
            )
            self.frame_length = self._porcupine.frame_length
            self.phrase = "ジャービス"
        elif engine == "openwakeword":
            import openwakeword
            from openwakeword.model import Model

            openwakeword.utils.download_models(model_names=["hey_jarvis"])
            self._oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            self.frame_length = 1280  # 80ms
            self.threshold = 1.0 - config.WAKEWORD_SENSITIVITY  # 感度0.6 → しきい値0.4
            self.phrase = "ヘイ、ジャービス"
        else:
            raise ValueError(f"WAKEWORD_ENGINE の値が不正です: {engine}")

    def _detect(self, pcm: np.ndarray) -> bool:
        if self.engine == "porcupine":
            return self._porcupine.process(pcm.tolist()) >= 0
        scores = self._oww.predict(pcm)
        if max(scores.values()) >= self.threshold:
            self._oww.reset()
            return True
        return False

    def wait(self) -> None:
        """ウェイクワードが聞こえるまでブロックする"""
        with sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=self.frame_length,
        ) as stream:
            while True:
                data, _ = stream.read(self.frame_length)
                if self._detect(data[:, 0]):
                    return

    def close(self) -> None:
        if self.engine == "porcupine":
            self._porcupine.delete()
