# 상태 기반 운영

아래 명령은 local-runtime.json의 Python으로 CLI를 실행한다. config의 실제 경로를 사용하고 shell 문자열 보간에 사용자 원문을 안전하지 않게 넣지 않는다. 구절은 인자로 따로 전달한다.

## 시작

```text
bnoc.py audit-bible
bnoc.py start "마태복음 1:1-5" --mode publish
bnoc.py start "창세기 12:1-3" --date 2026-10-25 --mode draft
bnoc.py status RUN_ID
bnoc.py claim RUN_ID --owner NATIVE_SESSION_ID
bnoc.py passage RUN_ID --token TOKEN
bnoc.py promote RUN_ID --token TOKEN
```

기본 실행일은 한국 날짜다. 주보 기반은 주보의 주일 날짜와 sunday-morning-adult service를 쓴다. 동일 날짜/본문/예배의 중복은 상태로 막는다. 사용자가 초안에서 게시로 바꾸라고 하면 아래 promote 명령으로만 전환한다.

## 주보 자동화

1. `check`는 금·토 06–22시 짝수 시각, 주일 06·08시에 처리한다. 수동 “주보 확인”에는 `check --force`를 사용한다.
2. outside-window/not-posted/already-published이면 짧게 끝낸다. 평범한 미변경 확인을 사용자에게 반복 보고하지 않는다.
3. needs-image-reading이면 candidate.json의 imageFiles를 실제로 열어 읽는다. 예배일, 오전 1·2·3부, 본문, 설교 제목을 구분한다. OCR 문자열만으로 확정하지 않는다.
4. observation.json에 아래 형식으로 관찰을 기록한다. 오전 예배 본문이 다르거나 판독이 불명확하면 질문하고 게시하지 않는다.

```json
{"date":"2026-10-18","service":"sunday-morning-adult","passage":"누가복음 10:1-9","morningPassages":["누가복음 10:1-9"],"unambiguous":true,"visuallyConfirmed":true,"imageUrl":"candidate.images 중 실제 확인한 URL","evidence":"1면 주일예배 말씀 행에서 오전 1·2·3부가 병합된 셀의 본문을 읽음"}
```

5. `observe CANDIDATE_JSON OBSERVATION_JSON`으로 등록한다. 기존 발행본이면 종료하고 새 제작을 시작하지 않는다. resume-required이면 run status를 읽고 재개한다.
6. 잠금이 유효하면 다른 실행을 시작하지 않는다. 만료 상태는 실제 실행이 끝났는지 확인한 후 `claim --resume-expired`로 재개한다. 실패 후에는 바뀐 증거/가설을 --changed-evidence에 명시한다.
7. 새 주일 주보가 없으면 지난 본문을 예측하지 않는다. 장기간 꺼져 있었으면 최근 미처리 주일 하나만 처리한다.

## 제작과 검토

각 run 폴더에 passage.json, research.md, manuscript.json, editorial-review.json, visual-plan.json, 필요한 그림, review.json을 둔다. content-first.md에 따라 글부터 검토한다. 실제 모델 ID를 기록하되 런타임이 공개하지 않은 세부 버전은 추정하지 않는다. 각 단계 완료 시 checkpoint로 파일 경로/확인 내용을 남긴다. written은 실제 원고 검토, illustrated는 원고에 따른 시각 결정의 이행을 검사한다. illustrated라는 기존 상태 이름은 텍스트만인 구성의 검증도 포함한다.

render 전에 reading-axes.json을 직접 작성한다. [원래 분석 규격](original-analysis-contract.md)에 따라 orthodoxy/orthopraxy/application 각각의 실제 cardId·정확한 quote·공개 전환 설명 introduction·개별 판단 rationale을 적고 model/reviewedAt/blockingFindings를 기록한다. applicationScopes의 personal/community/public에도 실제 문단의 cardId·quote를 각각 연결한다. 세 축을 같은 카드 하나로 합치지 않는다. 코드가 문장 존재를 확인하는 것이 해석 검토를 대신하지 않는다. native 익명 카드는 기존 순서의 @ordinal:NN을 내부 결합에만 쓰며 HTML ID나 기존 메모 공간을 바꾸지 않는다. 세 축의 공통 목차와 실제 해설의 연결을 적용한 뒤 원고·그림·스크립트·메모의 원래 바이트를 역변환으로 확인한다. final review의 readingAxes 결합과 checks.readingAxes에는 실제 세 축의 내용 및 링크·접힌/요약 상태 이동 검토를 적는다.

```text
bnoc.py checkpoint RUN_ID --token TOKEN --stage researched --evidence "research.md의 출처와 주요 논쟁 확인"
bnoc.py checkpoint RUN_ID --token TOKEN --stage written --evidence "원고를 읽고 본문 근거와 해석의 한계를 검토"
bnoc.py optimize-images RUN_ID --token TOKEN
bnoc.py checkpoint RUN_ID --token TOKEN --stage illustrated --evidence "검토 후 결정한 시각 구성의 실제 이행 확인"
bnoc.py render RUN_ID --token TOKEN
bnoc.py render RUN_ID --token TOKEN --print-proof
bnoc.py validate RUN_ID --token TOKEN
bnoc.py publish RUN_ID --token TOKEN
bnoc.py verify RUN_ID --token TOKEN
bnoc.py release RUN_ID --token TOKEN
```

render.json의 해시를 review에 사용한다. 검토 항목은 manuscript.md에 설명되어 있다. mobileTables와 readerControls도 별도 필수 검사이며 [모바일 읽기 규약](mobile-reader.md)의 320/390px·큰 글자·장문 중 도구 접근·접기/요약/검색 후 펼침을 실제로 확인한다. 가로 스크롤이나 버튼 존재만으로 통과하지 않는다. 단순 파일 존재·모델 자체 점수만으로 품질 검토를 대체하지 않는다. 변경 후 과거 review는 사용할 수 없다.
optimize-images 전 원본 그림의 실제 inspection이 필요하며, 변환 후 비워진 inspection을 배포본의 육안 검토로 새로 작성해야 illustrated가 통과한다. [압축 절차](image-delivery.md)를 따른다. SVG·기존WebP·텍스트만인 구성은 변환 없이 보고된다.

브라우저가 시스템 인쇄 미리보기를 노출하지 않으면 --print-proof로 실제 인쇄 CSS를 적용한 비공개 print-proof.html을 만든 뒤 브라우저에서 확인한다. 제목·표·본문·그림과 어두운 테마의 인쇄 색을 검사하고, 페이지 나눔/실물 인쇄를 확인했는지는 검토 근거에 구별하여 적는다. proof는 공개하지 않는다. 다운로드 이벤트를 도구에서 확인할 수 없으면 링크의 실제 파일 응답과 메모 저장 상태를 확인하고 그 한계를 기록한다.

verify가 deploying/waiting이면 30–60초 후 확인하며, 사용자에게 배포 중임을 알린다. published만 완료다. push가 성공했는지 애매하면 무작정 다시 만들지 말고 같은 run으로 publish를 재개해 원격 manifest를 확인한다.

verify의 published 결과는 lease를 자동 해제한다. 이때 release를 다시 실행하지 않는다. 위 release 명령은 초안 완료나 게시 전 중단 등 아직 lease가 남은 경우에만 쓴다.

같은 주소의 과거 버전이 남을 수 있으므로, verify는 공개 HTML 외에도 index.json과 search.json의 제목·설명·개정 시각·개정 종류와 검색 본문 전체가 새 파일과 일치하는지 확인한다. waiting-for-live-archive이면 배포/캐시 반영을 기다린 뒤 같은 run으로 검증한다. 브라우저에서도 검색 버튼을 실행해 새 제목의 결과를 확인한다.

Pages의 대기 중 작업이 후속 게시로 cancelled가 되어도 오래된 배포를 재실행하지 않는다. verify는 main의 후속 성공 배포와 실제 Git 조상 관계를 확인한 뒤 동일 HTML·허브·검색 본문이 일치할 때만 게시 완료로 처리한다. 실패한 검사나 무관한 브랜치의 성공으로 통과시키지 않는다.

## 실패

세 관점 바로가기는 본문 위 안내와 기존 목차·검색 대화상자에 함께 표시한다. 요약 보기나 전체 접기 상태에서도 바로가기를 실행하면 해당 해설을 펼치고 키보드 초점을 이동해야 한다. 공적 적용이 실제로 부족하여 새 문단을 쓴 경우 applicationScopes의 해당 cardId는 @guide:application으로 기록해 기존 원고에 있던 설명과 구별할 수 있다. 새로 쓴 문장도 본문과 자료에 근거해 직접 검토하고, 단락 구분은 introduction의 빈 줄로 표시한다.

reading-axes.json의 최소 형태는 다음과 같다. 아래 예시는 형식 설명이며 해석·검토 완료 자료로 복제하지 않는다.

```json
{"model":"실제 사용 모델","reviewedAt":"실제 검토 시각","blockingFindings":[],"axes":{"orthodoxy":{"cardId":"실제 카드 ID","quote":"그 카드에 있는 정확한 문장","introduction":"이 본문의 정론 해석으로 들어가는 연결 문단","rationale":"직접 읽고 선택하거나 보강한 이유"},"orthopraxy":{"cardId":"다른 실제 카드 ID","quote":"실제 문장","introduction":"이 본문의 정행 해석 연결 문단","rationale":"개별 판단"},"application":{"cardId":"또 다른 실제 카드 ID","quote":"실제 문장","introduction":"개인·공동체·공적 적용으로 이어지는 설명","rationale":"세 적용 범위를 읽고 판단한 근거"}},"applicationScopes":{"personal":{"cardId":"실제 카드 ID","quote":"개인 적용 문장"},"community":{"cardId":"실제 카드 ID","quote":"공동체 적용 문장"},"public":{"cardId":"실제 카드 ID","quote":"공적 적용 문장"}}}
```

```text
bnoc.py fail RUN_ID --token TOKEN --reason "정확한 실패 원인" --changed-evidence "다음에 시험할 변경된 조건"
bnoc.py claim RUN_ID --owner SESSION --changed-evidence "이전 실패 이후 실제 바뀐 조건"
```

최초 실패 후 두 번까지만 자동으로 재시도한다. 도구가 없거나 출처가 불확실하면 실패 단계를 보존하고 알린다. 다른 주보/성경으로 몰래 대체하거나 기준을 낮춰 게시하지 않는다.

## 자원과 모델 업데이트

일반 텍스트 검사·JSON 조회는 가볍다. 임시 웹 서버·무거운 렌더는 fresh Achmage resource 정책을 확인하고 등록된 work/native session으로 실행한다. 실제 작업 완료 후만 정상 종료한다.

모델 변경은 스킬 문구 수정 없이 반영된다. 템플릿/규약 변경 때에는 회귀 본문(누가복음, 마태복음 족보, 히브리어 본문, 합본 절)으로 검토한다. 검증에서 낮아진 품질을 모델 이름만으로 통과시키지 않는다.
