# 원고와 검토 파일

manuscript.json은 저자의 글을 담는다. 섹션/카드 수는 자유롭다. cards는 내부 데이터 이름이며 고정된 분량의 카드로 원고를 끊으라는 뜻이 아니다. 각 section의 presentation:"essay"는 문단이 이어지는 테두리 없는 배치, 기본 disclosure는 경계가 있는 배치다. 두 배치 모두 기본 펼침·개별/전체 접기·요약·찾기를 제공한다. 레이아웃을 이유로 읽기 기능을 제거하지 않는다. 이 선택은 원고 검토 후 결정한다. intro와 summary도 실제 문장으로 쓴다. coverage 배열은 기존 파일과의 호환용이며 항목명을 넣는 것으로 해석 검토를 대신할 수 없다.

```json
{
  "title":"성경 본문과 해설 제목",
  "date":"2026-10-25",
  "description":"아카이브에 표시할 소개",
  "intro":"장면과 읽기의 출발점을 소개하는 문단",
  "passageSha256":"passage.json의 sha256",
  "coverage":["context","exposition","orthodoxy","orthopraxy","language","application","reflection","conclusion"],
  "sections":[{"id":"context","title":"본문에 맞게 쓴 소제목","cards":[{"id":"context-first","title":"카드 제목","summary":"요약 모드에서 읽을 핵심 문장","html":"<p>충분한 서술형 본문과 <a href=\"#ref-source-one\">출처</a>.</p>","figure":"선택적인 그림 ID"}]}],
  "heroFigure":"선택적인 표지 그림 ID",
  "figures":[{"id":"scene","file":"images/scene.png","kind":"generated-illustration","alt":"그림의 핵심 내용을 설명","caption":"본문 이해를 돕는 창작 삽화라는 설명"}],
  "sources":[{"id":"source-one","title":"실제로 확인한 자료명","url":"https://실제주소","usedFor":"이 자료가 뒷받침하는 구체적 주장"}],
  "practices":["이번 주에 할 수 있는 구체적인 행동"]
}
```

html은 p, h4, strong/b, em/i, blockquote/cite, ul/ol/li, table/thead/tbody/tr/td/th/caption, small/span, a, br, sup/sub만 허용한다. 코드·스크립트·임의 스타일·이벤트 속성은 금지된다. 원고에는 의미 있는 표와 실제 열 제목을 작성한다. 렌더러는 모바일에서 그 열 제목을 각 항목에 붙여 세로로 읽게 한다. 표의 열 제목·행 제목에는 scope를 사용한다. 내용을 줄이거나 원어를 잘라 표 폭에 끼워 맞추지 않는다.

그리스어는 span lang="grc", 히브리어는 span lang="he" dir="rtl"로 표시한다. 출처의 id는 영문 소문자/숫자/하이픈, 인용 링크는 #ref-ID다. 출처별 확인 내용을 research.md에 남긴다. figures는 빈 배열일 수 있다. 그림을 넣는 경우 위 예시에 content-first.md의 해시·실제 검토·provenance 필드를 추가해야 한다.

## review.json

모든 검사는 실제로 수행한 뒤 기록한다. 미실시 항목은 passed:false와 이유를 기록한다. renderer가 만든 render.json에서 manuscriptSha256, passageSha256, htmlSha256와 metrics 안의 editorialReviewSha256, visualPlanSha256를 복사한다. 파일이나 그림을 수정하면 새 render와 review가 필요하다. 텍스트만인 글의 visualAccuracy에는 선택한 구성과 그림 없는 결과가 일치하는지 확인한 내용을 적는다.

```json
{
  "manuscriptSha256":"실제 해시",
  "passageSha256":"실제 해시",
  "htmlSha256":"실제 해시",
  "model":"실제 실행 모델 식별자",
  "reviewedAt":"ISO 시각",
  "checkedSourceIds":["실제로 확인한 모든 출처 ID"],
  "blockingFindings":[],
  "checks":{
    "historicalAccuracy":{"passed":true,"evidence":"확인한 주장과 출처, 불확실성 처리"},
    "originalLanguages":{"passed":true,"evidence":"본문형/레마/형태/문맥 확인 내용"},
    "orthodoxyOrthopraxy":{"passed":true,"evidence":"둘을 연결한 문단과 오용을 피한 방식"},
    "layReadability":{"passed":true,"evidence":"설명 깊이·이해 가능성·반복 검토"},
    "citationsChecked":{"passed":true,"evidence":"링크가 실제 주장을 뒷받침하는지 확인"},
    "visualAccuracy":{"passed":true,"evidence":"실제 그림/도표를 눈으로 검토"},
    "mobileLightDark":{"passed":true,"evidence":"실제 브라우저에서 확인한 크기와 두 테마"},
    "mobileTables":{"passed":true,"evidence":"320/390px·22px 글자에서 전체 원어/설명/용례를 세로로 읽고 열 제목 대응·RTL·폭을 확인한 내용"},
    "readerControls":{"passed":true,"evidence":"장문 중 하단 도구 접근·개별/전체 접기·요약·검색 뒤 펼침/포커스·성경 항상 펼침 확인 내용"},
    "searchNotesDownload":{"passed":true,"evidence":"검색·메모·저장 링크 확인 결과"},
    "printLayout":{"passed":true,"evidence":"실제 인쇄 미리보기 또는 렌더 확인 결과"}
  }
}
```

검토를 통과시키려고 판정 값을 자동으로 true로 채우는 스크립트를 만들지 않는다. 모델이 미래에 발전해도 이 원칙은 유지한다.

카드별 tableLayout:"wide"는 데스크톱에서 긴 원어 설명 표의 폭을 확보하는 선택이다. 모바일에서는 auto/wide 모두 열 제목이 붙은 세로형으로 전환되어 모든 셀을 가로 스크롤 없이 읽어야 한다. 인쇄에서는 원래 표로 표시한다. 상세 검수는 [모바일 읽기 규약](mobile-reader.md)을 따른다.
성경 본문은 항상 펼쳐진 독립 영역으로 표시한다. scriptureCollapsible은 사용하지 않으며, 과거 원고에 있어도 렌더러가 접기 동작을 만들지 않는다. 요약 읽기에서도 성경 본문은 유지한다.

생성 삽화는 원본과 웹 배포본을 구별해 기록한다. [배포 압축](image-delivery.md)의 optimize-images 명령으로 PNG/JPEG를 해상도 유지 WebP 품질92와 비교해 실제 작아진 경우에만 내장한다. SVG·기존 WebP는 유지하고 글자·정밀 도표는 무손실 또는 keep을 선택한다. 원본을 덮어쓰지 않으며 provenance에 원본/배포 해시와 조건을 남긴다. 변환 시 그림 검토가 무효화되므로 배포본도 실제로 육안 확인한다. MIME은 실제 형식과 일치해야 한다. 그림 수를 모든 원고에 강제하지 않는다. 게시완료 후 원본의 GitHub 복구 보관과 원격 해시 검증을 마치면 로컬 원본·원고·완성본 사본을 정리한다.

HTML 저장 검토는 화면을 연 미리보기 주소뿐 아니라 저장 링크의 실제 href 경로를 요청해 최종 HTML의 바이트·해시와 비교한다. HTTP 무결성 확인과 브라우저 저장 이벤트 확인은 구별해 기록한다.
