# HTML 내장 그림의 WebP 배포 압축

원고 검토와 시각 계획, 실제 이미지 생성·원본 검수 뒤에 실행한다. 압축은 그림을 새로 그리는 과정이나 신학적 검토를 대신하지 않는다. HTML에 Base64로 내장하기 전에 실제 바이트를 줄이며, renderer는 image/webp MIME으로 내장한다. 확장자만 바꾸지 않는다.

```text
bnoc.py optimize-images RUN_ID --token TOKEN
bnoc.py optimize-images RUN_ID --token TOKEN --lossless
bnoc.py optimize-images RUN_ID --token TOKEN --quality 92
```

기본 품질92/effort4, 원래 해상도와 알파 투명도를 유지한다. PNG/JPEG만 후보이며, WebP가 더 커지면 원본을 유지하고 사유를 보고한다. SVG와 기존 WebP는 그대로 사용해 반복 손실을 피한다. 애니메이션·회전 태그가 있는 파일은 임의로 단일 프레임이나 다른 방향으로 바꾸지 않고 별도 검토 사유를 남긴다. 개별 figure에 deliveryCompression:"lossless" 또는 "keep"를 지정할 수 있으며, 기본 삽화는 "lossy", raster diagram은 "lossless"다. 글자나 작은 선이 중요한 그림은 무손실 또는 SVG/원본을 우선한다. 특정 절감률을 보장하지 않는다.

이 명령은 현재 manuscript.json의 검토와 시각 계획·원본 파일 검사 근거가 유효해야 실행된다. 원본 파일을 덮어쓰거나 지우지 않는다. images/optimized 아래 새 WebP를 만들고, 실제 작아진 경우에만 manuscript의 배포 파일과 해시를 교체한다. image-optimization.json에 원본/배포 바이트·해상도·해시·인코더 버전과 채택 사유를 기록한다. provenance.originalSha256은 보존한다.

변환 후 inspection.evidence와 reviewedAt은 비워지고 단계는 written으로 돌아간다. 배포본을 실제로 열어 얼굴·손·작은 선·문자·색·투명도를 확인한 뒤 해당 배포 해시와 실제 검토 시각·근거를 기록한다. 이후 illustrated checkpoint → render → 최종 브라우저 검토 → validate 순서다. 예전 그림의 검토를 새 파일의 검토라고 재사용하거나 passed:true를 자동 작성하지 않는다. 기존 render/review는 해시가 달라 사용할 수 없다. 게시된 run의 그림은 직접 바꾸지 않고 명시적 개정 run에서 처리한다.

인코더는 로컬 번들 Node.js와 sharp를 사용한다. load_workspace_dependencies가 반환하는 실제 설치 경로를 확인하고 비공개 config에 다음 형태로 등록한다. 공개 저장소에 컴퓨터의 절대 경로를 쓰지 않는다. 인코더가 없으면 변환한 척하거나 자동 설치하지 않는다.

```json
{"imageEncoder":{"node":"실제 Node 실행 파일 절대 경로","sharp":"실제 sharp 모듈 절대 경로"}}
```

인코딩·무거운 검증은 적용 중인 Achmage 자원 정책에 따라 등록한 resource-run으로 실행한다. 작업이 실제 종료된 뒤 release한다. 공개 게시가 완료된 원본은 검증된 GitHub 원격 보관물이 있을 때 로컬 사본을 정리할 수 있다.

기술 근거: [Google WebP FAQ](https://developers.google.com/speed/webp/faq), [sharp WebP 출력 옵션](https://sharp.pixelplumbing.com/api-output/). 실제 감량과 육안 검토는 매 원고의 파일로 확인한다.
