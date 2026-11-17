// SPDX-License-Identifier: GPL-2.0-or-later
#include "AudioCommon/SDLSoundStream.h"

#include <algorithm>
#include <array>

#include <SDL3/SDL_init.h>

#include "Common/Logging/Log.h"

SDLSoundStream::~SDLSoundStream()
{
  if (m_stream)
  {
    SDL_DestroyAudioStream(m_stream);
    SDL_QuitSubSystem(SDL_INIT_AUDIO);
  }
}

bool SDLSoundStream::Init()
{
  if (!SDL_InitSubSystem(SDL_INIT_AUDIO))
  {
    ERROR_LOG_FMT(AUDIO, "SDL audio initialization failed: {}", SDL_GetError());
    return false;
  }

  SDL_AudioSpec spec{};
  spec.format = SDL_AUDIO_S16;
  spec.channels = 2;
  spec.freq = static_cast<int>(m_mixer->GetSampleRate());
  m_stream = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, Fill, m_mixer.get());
  if (!m_stream)
  {
    ERROR_LOG_FMT(AUDIO, "SDL audio stream failed: {}", SDL_GetError());
    SDL_QuitSubSystem(SDL_INIT_AUDIO);
  }
  return m_stream != nullptr;
}

bool SDLSoundStream::SetRunning(bool running)
{
  if (!m_stream)
    return false;
  if (running)
    return SDL_ResumeAudioStreamDevice(m_stream);
  return SDL_PauseAudioStreamDevice(m_stream);
}

void SDLSoundStream::SetVolume(int volume)
{
  if (m_stream)
    SDL_SetAudioStreamGain(m_stream, std::clamp(volume, 0, 100) / 100.0f);
}

void SDLCALL SDLSoundStream::Fill(void* userdata, SDL_AudioStream* stream, int additional, int)
{
  constexpr int channels = 2;
  constexpr int bytes_per_frame = channels * sizeof(s16);
  auto& mixer = *static_cast<Mixer*>(userdata);
  std::array<s16, 512 * channels> samples;
  int frames_remaining = additional / bytes_per_frame + (additional % bytes_per_frame != 0);
  while (frames_remaining > 0)
  {
    const int frames = std::min(frames_remaining, static_cast<int>(samples.size() / channels));
    mixer.Mix(samples.data(), frames);
    if (!SDL_PutAudioStreamData(stream, samples.data(), frames * bytes_per_frame))
      return;
    frames_remaining -= frames;
  }
}
