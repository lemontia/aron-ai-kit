# 효과음 세트

아론AI 롱폼에 실제로 쓰는 효과음 9개입니다. 모두 Freesound 의 CC0 녹음이라 출처 표기 없이 써도 됩니다(아래에 출처를 적어 두었습니다).

## 파일

| 파일 | 소리 | 언제 |
|---|---|---|
| tok_a · tok_b · tok_c | 톡 | 화면에 요소가 나타날 때. 셋을 번갈아 써서 같은 소리가 반복되지 않게 |
| swish | 휙 | 화면이 옮겨 갈 때, 장 제목 바로 앞 |
| tak | 탁 | 도장을 찍을 때 |
| tick | 째깍 | 숫자가 올라가는 동안 |
| chime2 | 띵 | 숫자를 다 센 순간 |
| chime3 | 띵(장) | 장 제목이 뜰 때 |
| glass | 띵(인용) | 결론 인용 화면이 뜰 때 |

## 놓는 규칙

1. **말 위에 얹지 않습니다.** 효과음이 말과 동시에 나면 그 음절이 묻힙니다. 톡·휙이 말 위에 떨어지면 바로 앞 쉼(화면보다 0.6초 먼저부터 0.25초 늦게까지)으로 옮기고, 옮길 쉼이 없으면 뺍니다.
2. **남는 소리는 목소리가 나는 동안 낮춥니다.** 째깍·띵·탁은 그대로 두되, 목소리를 기준으로 효과음 전체를 15dB 쯤 낮춥니다(덕킹).
3. **0.5초 안에 둘이 겹치면 센 쪽 하나만** 둡니다(띵(장)·띵(인용) > 띵 > 탁 > 휙). 째깍은 세는 소리라 겹쳐도 둡니다.
4. **과하다 싶으면 크기보다 횟수를 줄입니다.**
5. 휙은 화면이 바뀌는 순간에 가장 크게 들리도록 0.15초 먼저 시작합니다.

## 크기

- 파일은 이미 서로 크기를 맞춰 두었습니다(최고점 기준 톡·째깍 -20 · 휙 -13 · 탁 -11 · 띵 셋 -8.1 dBFS).
- 영상에 넣을 땐 효과음 트랙 전체를 목소리의 **0.35배**로 둡니다.

ffmpeg 로 덕킹할 때 쓰는 값입니다(효과음 `sfx.m4a`, 목소리 `voice.mp3`).

```bash
ffmpeg -i sfx.m4a -i voice.mp3 -filter_complex \
  "[1]aformat=sample_rates=48000:channel_layouts=stereo[v];[0][v]sidechaincompress=threshold=0.012:ratio=12:attack=3:release=90:makeup=1[o]" \
  -map "[o]" sfx_ducked.m4a
```

## 출처 (모두 CC0)

| 파일 | 원본 | 만든 이 |
|---|---|---|
| tok_a · b · c | [3 Popping Pops](https://freesound.org/people/wubitog/sounds/188381) 컷 1 · 2 · 3 | wubitog |
| swish | [27.wav](https://freesound.org/people/adcbicycle/sounds/14175) | adcbicycle |
| tak | [Thud 2.wav](https://freesound.org/people/nebulasnails/sounds/405537) | nebulasnails |
| tick | [Clock Tick (Tik Tak)](https://freesound.org/people/KaosMakinesi/sounds/403001) | KaosMakinesi |
| chime2 | [ding.wav](https://freesound.org/people/Daphne_in_Wonderland/sounds/127149) | Daphne_in_Wonderland |
| chime3 | [Soft-Notifications - Bell - Ding-Dong](https://freesound.org/people/LegitCheese/sounds/571513) | LegitCheese |
| glass | [Glass ding](https://freesound.org/people/Counter-gamer/sounds/404104) | Counter-gamer |

원본에서 잘라 크기만 맞췄습니다.
