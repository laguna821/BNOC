# 기존 자료 리메이크

기존 글 개선 요청에만 사용한다. 신규 주보 제작 권한을 과거 자료 일괄 변경 권한으로 확대하지 않는다.

자료별 날짜·본문·원본 경로·관련 Chat·개선 근거를 private state에 기록한다. 디자인(design), 신학적 내용(theology), 설명 분량(expansion)을 따로 판정한다. 글자 수는 참고 지표이며 부족 판정이 아니다. 팝업/스크립트에 담긴 해설과 퀴즈도 읽는다.

리메이크의 첫 기준은 원구절을 깊이 해설하고 성찰하는가이다. 이미 충실한 글이면 keep 또는 필요한 디자인 수정만 선택한다. 이번 주 최신본의 레이아웃·SameTone·원어 폰트·위계·그림 구성을 디자인의 기본으로 활용한다. 본문별 해석·충분한 설명·묵상·고찰에 맞춰 구성과 그림 수를 추가·변경할 수 있다. 최신본의 분량이나 구조를 맞추려고 원고를 끼워 넣지 않는다. 내용 개정은 content-first.md의 원고 검토를 먼저 거친다.

당시 Chat의 사용자 최종 수정 요청과 설교 자료를 확인한다. 날짜가 같다는 이유만으로 설교 노트를 제작 의도로 간주하지 않는다. 설교 맞춤 주제는 보존하고, 역사·원어 오류는 근거로 바로잡으며 설교자의 발언과 연구자의 보충을 구분한다. 미회수 맥락은 미확인으로 남기고 원래 주제를 임의 교체하지 않는다. 개인 대화·설교 원고는 공개 저장소에 넣지 않는다.

실행:

```text
bnoc.py revise YYYY/MMDDYYYY/file.html "민수기 18:21-32" --date 2025-08-17 --kinds design theology expansion --intent "확인한 제작 의도와 보존할 사항" --mode publish
```

claim 이후 통상 제작 절차를 따른다. manuscript.revision은 run.revision의 originalCommit/originalSha256/revisedAt/kinds만 복사한다. review.preservedIntent는 run.revision.intent와 일치해야 한다. 원본 변경이 감지되면 기존 작업에 덮어쓰기를 강행하지 말고 변경 내용을 대조한다.

design만 지정하면 original.html에 공통 글꼴·위계 CSS만 더한다. 이 경로는 원문·스크립트·ID·상호작용 속성 동일성을 검사한다. render.json의 해시와 model/reviewedAt/preservedIntent/ blockingFindings를 기록하고 contentPreserved, mobileLightDark, originalLanguages, searchNotesDownload, printLayout을 실제 검사한다. 디자인 검토로 신학적 정확성까지 검증됐다고 보고하지 않는다. 기존 기능이 없는 경우 새 기능을 사용했다고 기록하지 않는다.

원래 날짜·URL은 유지하며 개정일만 별도 표시한다. publish는 원본 해시와 검토를 다시 검사하고 특정 문서와 개정 manifest만 교체한다. 재시도는 같은 run을 사용한다. 이전 버전은 originalCommit의 Git blob으로 복구할 수 있다. 실제 배포와 홈페이지 검색까지 확인해야 완료다.

배치 실행은 private remake 목록에 pending/working/published/held/keep을 기록해 재개한다. 첫 대표 사례에서 발견한 문제를 해결한 뒤 다음 글로 진행한다. 미래 모델이 개선되어도 기존 제작 의도와 검토 근거는 생략하지 않는다.

성경 본문은 항상 펼쳐진 영역이어야 한다. 과거 BNOC 렌더러가 만든 정확한 접이식 본문만 고칠 때는 --kinds scripture로 독립 개정한다. 이 경로는 본문 접기 제어만 없애고 구절·해설·그림·스크립트·메모 키를 보존하며, 알 수 없는 HTML 구조는 거절한다. design 경로와 같은 실제 화면 검토와 해시 검증 후 게시한다. 다른 개정 종류와 혼합하지 않는다.
