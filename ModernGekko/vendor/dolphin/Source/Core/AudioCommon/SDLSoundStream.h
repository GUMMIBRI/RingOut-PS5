// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <SDL3/SDL_audio.h>

#include "AudioCommon/SoundStream.h"

class SDLSoundStream final : public SoundStream
{
public:
  static constexpr char BACKEND_NAME[] = "SDL";

  ~SDLSoundStream() override;
  bool Init() override;
  bool SetRunning(bool running) override;
  void SetVolume(int volume) override;

private:
  static void SDLCALL Fill(void* userdata, SDL_AudioStream* stream, int additional, int total);

  SDL_AudioStream* m_stream = nullptr;
};
