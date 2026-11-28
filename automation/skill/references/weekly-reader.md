# 주일 말씀 발행

장치 설정은 기존 bnoc-publish의 references/local-runtime.json이 가리키는 config.json이다. weeklyReader의 root, skill, version, sha256이 이 프로젝트의 유일한 제작 원본이다. 아래의 bnoc.py와 passage_weekly.py는 장치 설정의 weeklyReader.publisherDir에서 실행한다. 시작할 때 passage_weekly.py profile로 전체 묶음을 확인하고, 실패하면 그 이유를 남긴다. 스킬 버전은 bnoc-passage-reader 1.2.0이다.

1. bnoc.py check로 해당 주일 주보를 찾는다. 이미 게시한 동일 주보면 종료한다. 주보 원본 이미지에서 날짜와 오전 장년예배 1·2·3부를 각각 확인한다. 본문이 다르거나 판독이 모호하면 게시를 보류한다. observe, claim을 통해 기존 발행 식별자와 작업 잠금을 사용한다. 중단 뒤 재개는 기존 작업 경로와 실패 증거를 확인한다.
2. passage_weekly.py prepare --run-id ID --token TOKEN으로 비공개 작업 폴더와 검증된 스킬 경로를 얻는다. 원본 SKILL.md와 지시한 참조를 읽고 입력 본문, 준비서, 자료와 원고를 5판으로 새로 작성한다. 예화는 직접 찾고 출처를 연다. 실행 중인 모델의 새 대화에 review-request.md와 비공개 작업 폴더만 건네 독립 검수한다. 지적을 고친 뒤 검토자가 다시 읽고 seal한다. 사용자에게 추가 모델 API 비용을 발생시키지 않는다.
3. Achmage에 등록한 resource-run으로 passage_weekly.py render --run-id ID --token TOKEN을 실행한다. 메시지 렌더러가 만든 HTML·나눔 파일의 실제 글꼴·색상, 모바일·데스크톱 장 넘김, 낱말 열기, 밝기 전환, 공개 URL과 공유 정보를 직접 확인한다. 출력 내용이 바뀌면 다시 검수한다.
4. 최신 origin/main을 바탕으로 독립된 관리 작업 트리를 사용한다. passage_weekly.py stage --checkout 관리작업트리 --run-id ID --token TOKEN으로 충돌과 Git 바이트를 검사하고 지정된 파일만 스테이징한다. reading.html은 relativePath에, 나머지는 같은 폴더에 원래 이름으로 설치한다. publication.json은 issues/ID.json으로 저장한다. 게시 전 같은 날짜·예배의 다른 글, 기존 공유 자산과의 충돌을 확인한다. 이미 배포된 동일 해시는 재전송 없이 확인한다. 기존 파일이 다르면 공개를 보류한다. 명시적으로 철거한 교체 대상은 withdrawn-pending-replacement 발행 기록의 ID와 relativePath가 모두 일치할 때만 교체한다. 구판 Release는 보존한다.
5. Pages 빌드와 두 테스트 묶음, 실제 공개 파일 전체 해시와 제목·검색 색인을 로컬에서 확인한다. 묶음 전체, 성경 데이터, 주보 원본, 예화 출처 조사, audit, 장치 설정은 공개하지 않는다. 스테이징 목록·diff와 커밋 검증 영수증을 확인한 뒤 단일 main 변경을 Achmage remote_change_prepare, stable launcher remote-change-run으로 전송한다. 원격 상태가 불명확하면 조회한다.
6. Actions의 정확한 커밋/성공 결과를 remote_change_record에 남긴다. 실제 주소, 최신·허브·RSS·사이트맵, 검색 결과, HTML 및 공유 파일 해시를 확인하고 passage_weekly.py confirm --run-id ID --token TOKEN --commit DEPLOYED_SHA으로 로컬 발행 상태와 잠금을 확정한다. 도중에 재시작되면 원격을 관찰해 같은 건을 완료한다. 받은 설정의 시간표 및 기존 대상 대화를 따른다.
