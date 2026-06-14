"""ALTextToSpeech / ALAnimatedSpeech / ALSpeechRecognition wrapper."""

from __future__ import print_function


def _best_word(word_recognized):
    """ALMemory's 'WordRecognized' is [word1, conf1, word2, conf2, ...]."""
    if not isinstance(word_recognized, list) or len(word_recognized) < 2:
        return "", 0.0

    best_w, best_c = "", 0.0
    for i in range(0, len(word_recognized) - 1, 2):
        word = word_recognized[i]
        conf = word_recognized[i + 1]
        if isinstance(conf, (int, float)) and conf > best_c:
            best_w, best_c = word, float(conf)
    return best_w, best_c


class SpeechService(object):
    """Wraps ALTextToSpeech, ALAnimatedSpeech and ALSpeechRecognition.

    ALAnimatedSpeech and ALSpeechRecognition are optional: if a robot/SDK
    doesn't provide them, the corresponding proxy is None and the relevant
    methods either fall back (say) or raise a clear error (ASR methods).
    """

    _ASR_SUBSCRIBER = "nao_bridge_asr"

    def __init__(self, proxies):
        self._tts = proxies["ALTextToSpeech"]
        self._animated = proxies.get("ALAnimatedSpeech")
        self._asr = proxies.get("ALSpeechRecognition")
        self._memory = proxies.get("ALMemory")
        self._asr_subscribed = False

    def say(self, text, mode="animated", body_language_mode="contextual"):
        if mode == "animated" and self._animated is not None:
            self._animated.say(text, {"bodyLanguageMode": body_language_mode})
        else:
            self._tts.say(text)
        return {"ok": True}

    def set_language(self, language):
        self._tts.setLanguage(language)
        if self._asr is not None:
            self._asr.setLanguage(language)
        return {"ok": True}

    def set_volume(self, volume):
        self._tts.setVolume(volume)
        return {"ok": True}

    def asr_set_vocabulary(self, words, word_spotting=True):
        if self._asr is None:
            raise RuntimeError("ALSpeechRecognition is not available on this robot")

        was_subscribed = self._asr_subscribed
        if was_subscribed:
            self.asr_unsubscribe()

        self._asr.pause(True)
        self._asr.setVocabulary(list(words), bool(word_spotting))
        self._asr.pause(False)

        if was_subscribed:
            self.asr_subscribe()
        return {"ok": True}

    def asr_subscribe(self):
        if self._asr is None:
            raise RuntimeError("ALSpeechRecognition is not available on this robot")
        if not self._asr_subscribed:
            self._asr.subscribe(self._ASR_SUBSCRIBER)
            self._asr_subscribed = True
        return {"ok": True}

    def asr_unsubscribe(self):
        if self._asr is not None and self._asr_subscribed:
            self._asr.unsubscribe(self._ASR_SUBSCRIBER)
            self._asr_subscribed = False
        return {"ok": True}

    def asr_get_last_recognized(self):
        if self._memory is None:
            raise RuntimeError("ALMemory is not available on this robot")
        word, confidence = _best_word(self._memory.getData("WordRecognized"))
        return {"word": word, "confidence": confidence}


class MockSpeechService(object):
    """In-memory stand-in for SpeechService - prints instead of speaking."""

    def __init__(self):
        self.language = "English"
        self.volume = 1.0
        self.vocabulary = []
        self.subscribed = False
        self.spoken = []

    def say(self, text, mode="animated", body_language_mode="contextual"):
        print("[MOCK SAY] ({0}/{1}) {2}".format(mode, body_language_mode, text))
        self.spoken.append(text)
        return {"ok": True}

    def set_language(self, language):
        self.language = language
        return {"ok": True}

    def set_volume(self, volume):
        self.volume = volume
        return {"ok": True}

    def asr_set_vocabulary(self, words, word_spotting=True):
        self.vocabulary = list(words)
        return {"ok": True}

    def asr_subscribe(self):
        self.subscribed = True
        return {"ok": True}

    def asr_unsubscribe(self):
        self.subscribed = False
        return {"ok": True}

    def asr_get_last_recognized(self):
        return {"word": "", "confidence": 0.0}
