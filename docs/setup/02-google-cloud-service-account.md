# Google Cloud Service Account 셋업

Google Sheets를 코드에서 자동으로 읽고 쓰기 위해 Service Account가 필요합니다.

## 1. Google Cloud 프로젝트 생성
1. https://console.cloud.google.com/ 접속
2. 상단 프로젝트 선택 → "New Project" → 이름: `bible-bot` (예시)

## 2. Sheets API 활성화
1. "APIs & Services" → "Library"
2. "Google Sheets API" 검색 → "Enable"
3. "Google Drive API" 도 동일하게 Enable (시트 접근에 필요)

## 3. Service Account 생성
1. "APIs & Services" → "Credentials" → "Create credentials" → "Service account"
2. 이름: `bible-bot-runner` → "Create and continue"
3. Role: 비워두고 "Done"

## 4. JSON 키 발급
1. 방금 만든 Service Account 클릭 → "Keys" 탭 → "Add Key" → "Create new key" → JSON
2. 자동 다운로드되는 JSON 파일 저장 (예: `bible-bot-creds.json`)
3. **GitHub Secret 이름**: `GOOGLE_SHEETS_CREDS` (JSON 전체 내용을 복붙)

## 5. Google Sheet 생성 + 공유
1. https://sheets.google.com → 새 스프레드시트 생성 → 이름 `bible-bot-schedule`
2. URL에서 Sheet ID 복사 (예: `https://docs.google.com/spreadsheets/d/`**`1AbCdEf...`**`/edit`)
3. **GitHub Secret 이름**: `GOOGLE_SHEET_ID`
4. 시트 우상단 "Share" → Service Account 이메일(JSON의 `client_email` 필드)을 **편집자**로 추가

## 6. 시트 탭 만들기
다음 3개 탭을 만들어주세요 (탭 이름이 정확해야 함):
- `schedule`
- `meaningful_days`
- `config`

각 탭의 헤더와 초기값은 Task 13에서 자동으로 채워집니다.
