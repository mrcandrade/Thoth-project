"""Agente conversacional do Marco (Fase 1: voz — escutar, pensar, falar).

Pipeline: microfone -> VAD -> STT -> LLM (cérebro plugável) -> Piper (TTS).
Cérebro via endpoint OpenAI-compatible (Cerebras/Groq agora; Rio-3.5-397B depois).
"""
