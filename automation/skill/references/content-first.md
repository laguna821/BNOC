# 해석이 먼저인 제작과 검토

## 판단 순서

원구절과 앞뒤 문맥을 읽고, 실제 확인한 자료로 핵심 주장·원어·논쟁을 검토한다. 일반 성도가 이해할 연결된 해설을 먼저 쓴다. 정론·정행·현대 적용은 본문에 답하는 관점이며 고정된 세 카드가 아니다.

원고를 읽으며 다음을 묻는다. 본문의 무엇이 이 해석을 지지하는가? 다른 읽기가 가능한 지점은 어디인가? 전통의 설명과 현대적 제안을 구분했는가? 적용이 본문의 낯선 목소리를 지우지 않는가? 이 본문이 아니어도 할 수 있는 말로 페이지를 채우지 않았는가? 원어가 실제 이해를 더하는가? 설명이 생략되어 평신도가 따라가기 어려운 곳은 없는가?

고정 점수·분량·항목 존재·모델 체급으로 합격시키지 않는다. 아래 파일은 실제 읽고 판단한 근거를 남기는 기록이다. 코드가 해석의 옳음을 증명하지는 않는다. 미해결 문제가 크면 decision을 revise로 두고 디자인으로 진행하지 않는다.

## editorial-review.json

- contentSha256: editorial.content(manuscript)의 digest. 제목·도입·각 문단·요약·실천·출처를 포함하며 그림/표시 방식은 제외한다.
- passageSha256: 검증한 성경 본문의 해시.
- model, reviewedAt: 실제 검토 환경과 시간대가 있는 ISO 시각.
- decision: ready-for-design 또는 revise.
- thesis: 이 본문에서 읽어 낸 중심 논지와 범위.
- preservationDecision: 기존 글에서 보존/수정한 이유. 새 글이면 새 원고임을 명시.
- blockingFindings: 해결되지 않아 진행을 막는 문제 목록.
- checkedSourceIds: 실제 대조한 출처 ID.
- assessments: textAndContext, orthodoxy, orthopraxy, application, originalLanguages, readerDepth. 각 항목에 rationale(구체적 판단과 한계)와 anchors 배열을 쓴다. 각 anchor는 cardId와 해당 원고에서 인용한 정확한 짧은 quote다. 한 문단이 여러 관점을 다룰 수 있다. 별도의 고정 소제목을 요구하지 않는다.

원고를 바꾸면 다시 읽고 새 판단을 기록한다. 해시만 갱신하는 승인 스크립트를 만들지 않는다. 구조가 맞다는 것은 기록이 해당 글에 연결되었다는 뜻이며 신학적 품질 보증이 아니다.

## visual-plan.json

원고 검토 후 작성한다. contentSha256, editorialReviewSha256, decidedAt, mode(text-only 또는 illustrated), rationale, items를 담는다. 각 item은 id, kind, at(hero 또는 실제 cardId), purpose다. 본문 이해에 도움이 되는 이유를 설명한다. 텍스트만이면 items는 빈 배열이다.

그림을 계획했으면 실제 파일을 만들고 배치한다. 만든 뒤 맞지 않는다고 판단하면 억지로 쓰지 말고 계획을 근거와 함께 수정한다. 사용하지 않은 파일 자체는 보관할 수 있으나 manuscript.figures에는 내장할 것만 등록한다.

각 figure에 sha256, inspection:{sha256,reviewedAt,evidence}, provenance를 기록한다. 원고의 설명 뒤에 놓으려면 card.figurePosition과 해당 plan item.position을 모두 after로 지정한다(기본 before). 배치 때문에 원고를 다시 쓰지 않는다.
- generated-illustration: 실제 image_gen 호출의 tool, prompt, originalSha256, generatedAt. 결과를 직접 보고 원고에 맞는지 기록한다. 파일 형식 최적화 시 원본 해시를 보존한다.
- sourced-image: url, rights.
- diagram: basis(어떤 구절·데이터의 관계를 설명하는가).

계획과 등록 목록, 실제 내장 위치, 파일 해시와 육안 검토 기록을 검사한다. SVG를 생성 삽화라고 이름만 바꾸거나, 예정한 그림을 누락한 채 통과시키지 않는다. 실제 도구 결과가 없으면 생성했다고 기록하지 않는다.

## 디자인·최종 검토

이번 주 최신본의 레이아웃·폰트 위계·디자인·그림 구성을 기본 출발점으로 삼는다. 원구절의 신학적 해석·충분한 설명·묵상·고찰을 더 잘 전달하도록 추가하거나 바꿀 수 있다. SameTone Lite의 실제 가변 폰트(100–900)와 원어 대체 폰트를 보존한다. 제목·절 제목·소제목·본문·표·캡션의 의미에 따라 위계를 적용하고 모든 굵기를 억지로 사용할 필요는 없다. 공통 typography.css는 읽기 역할과 색상을 공유하며, 레이아웃은 본문에 따라 선택한다.

본문별 출력에서 실제 원어 표시와 모바일/데스크톱, 두 테마, 기능, 인쇄를 검사한다. 테마 표준을 공유해도 과거 글의 고유 클래스·상호작용 때문에 문제가 생길 수 있으므로 파일별 확인을 생략하지 않는다. 최종 review는 render의 해시 및 editorialReviewSha256·visualPlanSha256에 연결한다.
