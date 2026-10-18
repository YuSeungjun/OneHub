# OneHub

유튜브 영상과 오디오를 MP4 / MP3로 저장하는 Electron 앱입니다.
일반 영상, Shorts, YouTube Music 링크를 지원하며, 링크에 재생목록이나 라디오 정보가 있어도 선택한 영상 한 개만 저장합니다.

## 개발 환경

Node.js 22 이상, Python 3.13 이상, uv가 필요합니다.

```powershell
npm.cmd ci
uv sync --frozen
npm.cmd run dev
```

Electron은 프로젝트 `.venv`의 Python을 직접 실행합니다. 다른 서비스를 종료하지 않고 빈 로컬 포트를 선택합니다.
화면만 확인하려면 `npm.cmd run dev:vite`, 별도 API 실행은 `uv run python backend/main.py`를 사용합니다.
브라우저에서 저장 폴더 변경은 지원하지 않습니다.

## 검증과 설치 파일

```powershell
npm.cmd run lint
npm.cmd run test:backend
npm.cmd run test:electron
npm.cmd run build
```

Windows 설치 파일은 `installer/OneHub_Setup.exe`에 생성됩니다. macOS 빌드는 macOS에서 실행하세요.
빌드는 Python 백엔드, FFmpeg, yt-dlp EJS 스크립트와 빌드 머신의 Node 실행 파일을 함께 포함합니다.
사용자는 Python이나 Node를 별도로 설치할 필요가 없습니다.
백엔드는 폴더 방식으로 묶어 실행할 때마다 임시 폴더에 압축을 푸는 지연을 없앴습니다.
배포할 때는 `OneHub_Setup.exe`를 전달하세요. `win-unpacked/OneHub.exe`는 옆의 `resources` 등 전체 폴더가 함께 있어야 실행됩니다.
Electron은 설치된 npm 패키지의 실행 파일을 사용해 패키징합니다. 기존 OneHub가 실행 중이면 종료한 뒤 새 설치 파일을 실행하세요.

## 다운로드 오류 대응

YouTube의 JavaScript 검증에 맞춰 `yt-dlp[default]`와 지원되는 JavaScript 런타임을 사용합니다.
403 발생 시 캐시를 사용하지 않고 영상 URL을 다시 추출해 한 번 재시도합니다.
로그인·연령·지역·네트워크 제한 때문에 거부된 영상까지 다운로드를 보장하지는 않습니다.
인증 쿠키를 자동으로 읽거나 제한을 우회하지 않습니다.

다운로드 엔진 업데이트 후에는 설치 파일도 다시 빌드해야 합니다.

```powershell
uv lock --upgrade-package yt-dlp --upgrade-package yt-dlp-ejs
uv sync --frozen
npm.cmd run build
```

- 진행률은 현재 내려받는 영상/오디오 스트림 기준이며 병합·변환 단계는 별도로 표시합니다.
- 화면 상단 게이지에 받은 용량, 다운로드 속도, 예상 남은 시간을 표시합니다.
- 최종 파일 저장이 확인되면 완료 알림음이 한 번 울립니다. 게이지의 알림음 버튼으로 켜고 끌 수 있으며 설정은 유지됩니다.
- 취소는 해당 작업의 프로세스 트리와 `.onehub-*` 임시 디렉터리만 정리합니다.
- API는 유튜브 영상 URL과 지원되는 출력 형식을 검증합니다.
- Electron API는 실행마다 생성한 토큰으로 인증합니다.
- 상세 오류는 앱 데이터 폴더의 `onehub_debug.log`에서 확인합니다.

참고: [yt-dlp EJS 설정](https://github.com/yt-dlp/yt-dlp/wiki/EJS), [YouTube PO Token 안내](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide).
