# 원고와 검토 파일

manuscript.json은 레이아웃이 아니라 저자의 글을 담는다. 아래 필드만 필요하다. 섹션/카드 수는 자유롭다. intro와 summary도 실제 문장으로 쓴다.

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

html은 p, h4, strong/b, em/i, blockquote/cite, ul/ol/li, table/thead/tbody/tr/td/th/caption, small/span, a, br, sup/sub만 허용한다. 코드·스크립트·임의 스타일·이벤트 속성은 금지된다. table은 가로 스크롤이 가능한 span class="table-scroll"보다 CSS 블록형 컨테이너를 렌더러에서 자동 제공하므로 원고에는 의미 있는 표만 작성한다. 표의 열 제목·행 제목에는 scope를 사용한다.

그리스어는 span lang="grc", 히브리어는 span lang="he" dir="rtl"로 표시한다. 출처의 id는 영문 소문자/숫자/하이픈, 인용 링크는 #ref-ID다. 출처별 확인 내용을 research.md에 남긴다.

## review.json

모든 검사는 실제로 수행한 뒤 기록한다. 미실시 항목은 passed:false와 이유를 기록한다. renderer가 만든 render.json에서 manuscriptSha256, passageSha256, htmlSha256를 복사한다. 파일이나 그림을 수정하면 새 render와 review가 필요하다.

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
    "searchNotesDownload":{"passed":true,"evidence":"검색·메모·저장 링크 확인 결과"},
    "printLayout":{"passed":true,"evidence":"실제 인쇄 미리보기 또는 렌더 확인 결과"}
  }
}
```

검토를 통과시키려고 판정 값을 자동으로 true로 채우는 스크립트를 만들지 않는다. 모델이 미래에 발전해도 이 원칙은 유지한다.
