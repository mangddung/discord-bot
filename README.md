2024/04/28 약 6시간 작업 GPT 도움

게임 인원 모집하는 디스코드 봇

업데이트
----
24/5/9 

~~집중모드~~, 음성차단 기능 추가

서버 참여시 역할 생성 -> !역할생성, !역할삭제 명령어 추가

~~집중모드: 
역할에 등록된 사람은 평일 00~18시까지 음성채팅 참여시 강퇴~~

음성차단:
역할에 등록된 사람은 음성채팅 참여시 강퇴

----
24/6/23

모집 명령어 입력 양식으로 변경

해당 역할 멤버 없는 경우 역할 이름 표시 안함

---
24/6/24

하면함 역할 제거

역할 이름 변경 함, 안함 -> 참여, 불참

채널 권한 부여 기능 추가(DB사용)

관리자용 명령어 설명 추가

---
24/7/13

모집 게임 이름, 모집 인원 직접 입력에서 드롭다운 선택으로 변경(자주하는 게임으로 목록 구성)

---
24/7/23

권한부여 메세지 기능 오류 수정

봇 서버 입장시 역할 생성 기능 삭제

게스트 초대 기능 추가(초대 코드 생성, 게스트 초대 확인 후 권한 설정, 게스트 채널 이탈시 서버 추방)

로그 기록(모집 기능 제외 나머지 기능에 대해 대충 기록)

---
24/7/28

로그 기록 문제 해결

게스트 기능 개선(서버 입장시 권한 부여 -> 게스트 역할 부여, 대상 채널 권한 부여)

게스트 초대 코드 DB 초대 코드 생성, 게스트 참여 시간 필드 추가(시간대 한국)

---
24/11/05

취침모드(구 집중모드 역할) 기능 추가

취침모드 설정한 시간 1,5,30분 전에 DM으로 알림 전달

취침모드 설정한 시간내이면 음성채널 추방

취침모드설정, 취침모드켜기, 취침모드끄기 명령어 추가

---
24/11/10

Typecast.ai tts 기능 추가

/tts 명령어로 모달에 텍스트 입력시 접속중인 음성채널에 봇이 들어와 tts 실행

https://biz.typecast.ai/org/overview

위 링크에 접속해서 캐틱터 변경시 tts_character 변수에서 변경한 캐릭터 주석 해제, 나머지 캐릭터 주석 처리

명령어
----
!모집 : 모집 양식을 입력할 수 있는 버튼 메시지를 보냅니다.

!모집종료 : 모집을 종료합니다.

!명령어 : 도움말을 출력합니다.

!모임 : 모집이 완료된 경우 모임을 시작합니다.(멤버 멘션)

!재전송 : 모집 메시지를 재전송합니다.

!게스트 : 접속 중인 음성 채널에 손님 초대 링크를 생성합니다.

/취침모드설정 : 입력폼에 취침모드 설정을 입력합니다.

/취침모드켜기 : 취침모드를 켭니다.

/취침모드끄기 : 취침모드를 끕니다.

/tts : tts 텍스트 입력 모달을 띄웁니다. 

관리자 명령어

!역할생성 : 봇에서 사용하는 역할을 생성합니다.

!역할삭제 : 봇에서 사용하는 역할을 삭제합니다.

!채널생성 [채널명] : 권한 부여 채널을 생성합니다.

!메시지생성 [대상채널명] : 대상 채널에 권한 부여 메시지를 생성합니다.

!메시지삭제 [대상채널명] : 대상 채널에 권한 부여 메시지를 삭제합니다.
