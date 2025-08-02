"""
이 프로그램은 ESR-E개발보드에 연결된 모든 하드웨어 컴포넌트의
정상 작동을 확인하고 OLED 디스플레이에 결과를 표시하는 종합 테스트 시스템입니다.
"""

# ========== 필수 라이브러리 Import ==========
# MicroPython의 핵심 하드웨어 제어 모듈들을 import
import machine        # GPIO, PWM, ADC 등 하드웨어 제어를 위한 기본 모듈
import neopixel       # WS2812B LED 스트립 제어를 위한 전용 라이브러리
import time           # 시간 지연 및 타이밍 제어를 위한 모듈
import uos            # MicroPython 파일시스템 제어 모듈 (SD카드 마운트용)

# machine 모듈에서 세부 클래스들을 개별 import (코드 간소화)
from machine import Pin, PWM, ADC, I2C, SPI

# 외부 하드웨어 제어를 위한 특수 라이브러리들
import dht            # DHT22 온습도 센서 제어 라이브러리
import ssd1306        # SSD1306 OLED 디스플레이 제어 라이브러리
import sdcard         # SD카드 SPI 인터페이스 제어 라이브러리

# ========== GPIO 핀 정의 ==========
# Pico2 W의 GPIO 핀 번호를 각 하드웨어 컴포넌트에 매핑
# 이 방식으로 하드웨어 연결을 코드로 명확히 정의
WS2812B_PIN = 0       # WS2812B LED 스트립 데이터 입력 핀
OLED_SDA = 4          # OLED I2C 통신용 데이터 라인 (Serial Data)
OLED_SCL = 5          # OLED I2C 통신용 클럭 라인 (Serial Clock)
LED_R_PIN = 7         # RGB LED의 빨간색 PWM 제어 핀
LED_G_PIN = 6         # RGB LED의 초록색 PWM 제어 핀
LED_B_PIN = 8         # RGB LED의 파란색 PWM 제어 핀
BUTTON_PIN = 11       # 사용자 입력용 택트 스위치 핀
SD_CS = 17            # SD카드 SPI 칩 셀렉트 핀 (Chip Select)
SD_SCK = 18           # SD카드 SPI 클럭 핀 (Serial Clock)
SD_MOSI = 19          # SD카드 SPI 마스터 출력 핀 (Master Out Slave In)
BUZZER_PIN = 20       # 패시브 부저 PWM 출력 핀
DHT22_PIN = 22        # DHT22 온습도 센서 데이터 핀 (1-wire 통신)
LDR_PIN = 27          # LDR 조도 센서 아날로그 입력 핀
TRIMMER_PIN = 28      # 트리머 가변저항 아날로그 입력 핀
SD_MISO = 16          # SD카드 SPI 마스터 입력 핀 (Master In Slave Out)

# ========== 시스템 상수 정의 ==========
# 프로그램 전체에서 사용되는 주요 상수들을 정의
NUM_PIXELS = 10       # WS2812B LED 스트립에 연결된 개별 LED의 총 개수
TOTAL_PAGES = 4       # OLED 디스플레이에 표시할 페이지의 총 개수
DEBOUNCE_DELAY = 200  # 버튼 디바운싱을 위한 지연 시간 (밀리초)

# ========== 메인 컴포넌트 테스트 클래스 ==========
class ComponentTest:
    """
    모든 하드웨어 컴포넌트의 초기화, 테스트, 모니터링을 담당하는 메인 클래스
    객체지향 설계로 코드의 구조화와 재사용성을 높임
    """
    
    def __init__(self):
        """
        클래스 생성자: 객체 생성 시 자동으로 호출되어 초기 설정을 수행
        """
        
        # ========== 테스트 결과 저장용 딕셔너리 ==========
        # 각 하드웨어 컴포넌트의 상태와 센서 데이터를 체계적으로 관리
        self.test_results = {
            # 하드웨어 컴포넌트별 정상 작동 여부 (Boolean)
            'oled_ok': False,       # OLED 디스플레이 초기화 및 표시 상태
            'ws2812b_ok': False,    # WS2812B LED 스트립 제어 상태
            'sd_ok': False,         # SD카드 마운트 및 파일시스템 상태
            'dht22_ok': False,      # DHT22 온습도 센서 통신 상태
            'button_ok': False,     # 버튼 입력 감지 상태
            'buzzer_ok': False,     # 부저 PWM 출력 상태
            'ldr_ok': False,        # LDR 조도 센서 ADC 읽기 상태
            'trimmer_ok': False,    # 트리머 가변저항 ADC 읽기 상태
            'rgb_led_ok': False,    # RGB LED PWM 제어 상태
            
            # 센서에서 실제로 측정된 데이터 값들
            'temperature': 0.0,     # DHT22에서 읽은 온도 값 (섭씨)
            'humidity': 0.0,        # DHT22에서 읽은 상대습도 값 (%)
            'ldr_value': 0,         # LDR 센서의 ADC 원시값 (0-65535)
            'trimmer_value': 0      # 트리머의 ADC 원시값 (0-65535)
        }
        
        # ========== 프로그램 상태 관리용 인스턴스 변수들 ==========
        self.current_page = 0           # 현재 OLED에 표시 중인 페이지 번호 (0-3)
        self.last_button_time = 0       # 마지막 버튼 입력 시간 (디바운싱용)
        self.last_display_update = 0    # 마지막 디스플레이 업데이트 시간
        self.last_rainbow_update = 0    # 마지막 무지개 패턴 업데이트 시간
        self.color_index = 0            # 무지개 패턴의 현재 색상 인덱스
        
        # ========== 하드웨어 초기화 실행 ==========
        # 생성자에서 즉시 모든 하드웨어를 초기화하여 사용 준비 완료
        self.init_hardware()
        
    def init_hardware(self):
        """
        모든 하드웨어 컴포넌트를 순차적으로 초기화하는 메서드
        각 하드웨어별로 독립적인 예외 처리를 통해 일부 실패가 전체에 영향주지 않음
        """
        print("Raspberry Pi Pico2 W Component Test Starting...")
        
        # ========== I2C 통신 및 OLED 디스플레이 초기화 ==========
        try:
            # I2C 버스 0번을 400kHz 고속 모드로 초기화
            # SCL(클럭)과 SDA(데이터) 핀을 명시적으로 지정
            self.i2c = I2C(0, scl=Pin(OLED_SCL), sda=Pin(OLED_SDA), freq=400000)
            
            # SSD1306 OLED 컨트롤러를 128x64 해상도로 초기화
            self.oled = ssd1306.SSD1306_I2C(128, 64, self.i2c)
            
            # 초기화 성공 시 상태 업데이트
            self.test_results['oled_ok'] = True
            
            # 화면을 검은색으로 지우고 환영 메시지 표시
            self.oled.fill(0)                    # 0=검은색으로 화면 전체 채우기
            self.oled.text("Pico2 W Test", 0, 0) # 좌상단에 제목 표시
            self.oled.text("Initializing...", 0, 10) # 상태 메시지 표시
            self.oled.show()                     # 실제 화면에 출력
            print("OLED: OK")
            
        except Exception as e:
            # OLED 초기화 실패 시 에러 메시지 출력하지만 프로그램은 계속 진행
            print(f"OLED: FAIL - {e}")
            
        # ========== WS2812B LED 스트립 초기화 ==========
        try:
            # NeoPixel 객체 생성: 지정된 핀에 연결된 10개 LED 제어
            self.ws2812b = neopixel.NeoPixel(Pin(WS2812B_PIN), NUM_PIXELS)
            
            # 모든 LED를 (0,0,0) = 꺼진 상태로 초기화
            self.ws2812b.fill((0, 0, 0))
            
            # 실제 하드웨어에 색상 정보 전송
            self.ws2812b.write()
            
            # 초기화 성공 표시
            self.test_results['ws2812b_ok'] = True
            print("WS2812B: OK")
            
        except Exception as e:
            print(f"WS2812B: FAIL - {e}")
            
        # ========== DHT22 온습도 센서 초기화 ==========
        try:
            # DHT22 센서 객체 생성 (1-wire 통신 프로토콜 사용)
            self.dht22 = dht.DHT22(Pin(DHT22_PIN))
            
            # 센서 객체 생성이 성공하면 초기화 완료로 간주
            self.test_results['dht22_ok'] = True
            print("DHT22: OK")
            
        except Exception as e:
            print(f"DHT22: FAIL - {e}")
            
        # ========== 버튼 입력 초기화 ==========
        try:
            # 버튼을 내부 풀업 저항이 활성화된 입력 모드로 설정
            # 풀업 저항으로 인해 누르지 않으면 HIGH, 누르면 LOW 신호
            self.button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
            print("Button: OK")
            
        except Exception as e:
            print(f"Button: FAIL - {e}")
            
        # ========== 패시브 부저 PWM 초기화 ==========
        try:
            # 부저를 PWM 모드로 설정하여 다양한 주파수 톤 생성 가능
            self.buzzer = PWM(Pin(BUZZER_PIN))
            
            # 기본 주파수를 1000Hz로 설정
            self.buzzer.freq(1000)
            
            # duty_u16(0)으로 초기에는 소리가 나지 않도록 설정
            # duty_u16 범위: 0(0%) ~ 65535(100%)
            self.buzzer.duty_u16(0)
            
            self.test_results['buzzer_ok'] = True
            print("Buzzer: OK")
            
        except Exception as e:
            print(f"Buzzer: FAIL - {e}")
            
        # ========== RGB LED PWM 초기화 ==========
        try:
            # 각 색상(R, G, B)별로 별도의 PWM 객체 생성
            self.led_r = PWM(Pin(LED_R_PIN))
            self.led_g = PWM(Pin(LED_G_PIN))
            self.led_b = PWM(Pin(LED_B_PIN))
            
            # 모든 PWM을 1000Hz 주파수로 설정 (깜빡임 방지)
            self.led_r.freq(1000)
            self.led_g.freq(1000)
            self.led_b.freq(1000)
            
            # 초기에는 모든 LED를 꺼진 상태로 설정
            self.set_rgb_color(0, 0, 0)
            
            self.test_results['rgb_led_ok'] = True
            print("RGB LED: OK")
            
        except Exception as e:
            print(f"RGB LED: FAIL - {e}")
            
        # ========== ADC 아날로그 입력 초기화 ==========
        try:
            # LDR 조도 센서를 ADC 모드로 초기화
            self.ldr = ADC(Pin(LDR_PIN))
            
            # 트리머 가변저항을 ADC 모드로 초기화
            self.trimmer = ADC(Pin(TRIMMER_PIN))
            
            # 두 센서 모두 정상 초기화되면 상태 업데이트
            self.test_results['ldr_ok'] = True
            self.test_results['trimmer_ok'] = True
            print("ADC (LDR, Trimmer): OK")
            
        except Exception as e:
            print(f"ADC: FAIL - {e}")
            
        # ========== SD카드 SPI 통신 초기화 ==========
        try:
            # SPI 버스 0번을 1MHz 속도, 모드 0으로 초기화
            # polarity=0, phase=0은 SPI 모드 0을 의미 (SD카드 표준)
            self.spi = SPI(0, baudrate=1000000, polarity=0, phase=0,
                          sck=Pin(SD_SCK), mosi=Pin(SD_MOSI), miso=Pin(SD_MISO))
            
            # Chip Select 핀을 출력 모드로 설정
            self.cs = Pin(SD_CS, Pin.OUT)
            
            # SDCard 객체 생성 (SPI 통신 및 CS 핀 지정)
            self.sd = sdcard.SDCard(self.spi, self.cs)
            
            # SD카드를 '/sd' 경로로 마운트하여 파일시스템으로 접근 가능하게 설정
            uos.mount(self.sd, '/sd')
            
            self.test_results['sd_ok'] = True
            print("SD Card: OK")
            
        except Exception as e:
            print(f"SD Card: FAIL - {e}")
            
    def run_all_tests(self):
        """
        시스템 시작 시 모든 하드웨어 컴포넌트에 대해 기능 테스트를 수행
        각 테스트는 독립적으로 실행되어 일부 실패가 다른 테스트에 영향주지 않음
        """
        print("Running comprehensive tests...")
        
        # OLED가 정상 작동하는 경우에만 화면에 진행 상황 표시
        if self.test_results['oled_ok']:
            self.oled.fill(0)                        # 화면 지우기
            self.oled.text("Running Tests...", 0, 0) # 테스트 진행 메시지
            self.oled.show()                         # 화면에 출력
            
        # ========== 각 컴포넌트별 개별 테스트 실행 ==========
        # 각 테스트 함수는 독립적으로 동작하며 실패해도 다음 테스트 계속 진행
        self.test_dht22()      # DHT22 온습도 센서 데이터 읽기 테스트
        self.test_ldr()        # LDR 조도 센서 ADC 읽기 테스트
        self.test_trimmer()    # 트리머 가변저항 ADC 읽기 테스트
        self.test_buzzer()     # 부저 톤 출력 테스트
        self.test_rgb_led()    # RGB LED 색상 출력 테스트
        self.test_sd_card()    # SD카드 파일 읽기/쓰기 테스트
        
        print("All tests completed!")
        
    def test_dht22(self):
        """
        DHT22 온습도 센서의 데이터 읽기 기능을 테스트
        센서 특성상 안정화 시간이 필요하므로 2초 대기 후 측정
        """
        # 초기화가 실패한 경우 테스트를 건너뛰어 오류 방지
        if not self.test_results['dht22_ok']:
            return
            
        try:
            # DHT22 센서는 최소 2초의 안정화 시간이 필요
            time.sleep(2)
            
            # 센서에 측정 명령 전송
            self.dht22.measure()
            
            # 온도와 습도 데이터를 읽어와서 결과 딕셔너리에 저장
            self.test_results['temperature'] = self.dht22.temperature()
            self.test_results['humidity'] = self.dht22.humidity()
            
            # 측정 결과를 소수점 1자리까지 포맷하여 출력
            print(f"DHT22: T={self.test_results['temperature']:.1f}°C, "
                  f"H={self.test_results['humidity']:.1f}%")
                  
        except Exception as e:
            # 센서 읽기 실패 시 에러 출력하고 상태를 False로 변경
            print(f"DHT22 read: FAIL - {e}")
            self.test_results['dht22_ok'] = False
            
    def test_ldr(self):
        """
        LDR(Light Dependent Resistor) 조도 센서의 ADC 읽기 테스트
        16비트 ADC를 사용하여 0-65535 범위의 값을 읽음
        """
        if not self.test_results['ldr_ok']:
            return
            
        try:
            # read_u16()으로 16비트 부호없는 정수 값 읽기
            # 0 = 최대 저항(어두움), 65535 = 최소 저항(밝음)
            self.test_results['ldr_value'] = self.ldr.read_u16()
            print(f"LDR: {self.test_results['ldr_value']}")
            
        except Exception as e:
            print(f"LDR: FAIL - {e}")
            self.test_results['ldr_ok'] = False
            
    def test_trimmer(self):
        """
        트리머 가변저항의 ADC 읽기 테스트
        사용자가 회전시킨 위치에 따라 0-65535 범위의 값 출력
        """
        if not self.test_results['trimmer_ok']:
            return
            
        try:
            # 트리머의 현재 위치를 16비트 해상도로 읽기
            self.test_results['trimmer_value'] = self.trimmer.read_u16()
            print(f"Trimmer: {self.test_results['trimmer_value']}")
            
        except Exception as e:
            print(f"Trimmer: FAIL - {e}")
            self.test_results['trimmer_ok'] = False
            
    def test_buzzer(self):
        """
        패시브 부저의 톤 출력 기능 테스트
        서로 다른 주파수의 톤을 순차적으로 재생하여 정상 작동 확인
        """
        if not self.test_results['buzzer_ok']:
            return
            
        try:
            # ========== 부저 테스트 멜로디 재생 ==========
            # 1500Hz 톤을 200ms 동안 재생
            self.play_tone(1500, 200)
            time.sleep_ms(100)    # 톤 사이의 간격
            
            # 2000Hz 톤을 200ms 동안 재생
            self.play_tone(2000, 200)
            time.sleep_ms(100)    # 완료 후 대기
            
            print("Buzzer: Test completed")
            
        except Exception as e:
            print(f"Buzzer: FAIL - {e}")
            self.test_results['buzzer_ok'] = False
            
    def test_rgb_led(self):
        """
        RGB LED의 각 색상 채널 출력 테스트
        빨강, 초록, 파랑, 흰색 순서로 표시하여 모든 채널 정상 동작 확인
        """
        if not self.test_results['rgb_led_ok']:
            return
            
        try:
            # ========== 순차적 색상 테스트 ==========
            # 각 색상을 300ms씩 표시하여 사용자가 변화를 인지할 수 있도록 함
            colors = [(255, 0, 0),    # 빨간색 (R=최대, G=0, B=0)
                     (0, 255, 0),     # 초록색 (R=0, G=최대, B=0)
                     (0, 0, 255),     # 파란색 (R=0, G=0, B=최대)
                     (255, 255, 255)] # 흰색 (R=최대, G=최대, B=최대)
            
            # 각 색상을 순차적으로 표시
            for r, g, b in colors:
                self.set_rgb_color(r, g, b)
                time.sleep_ms(300)
                
            # 테스트 완료 후 LED 끄기
            self.set_rgb_color(0, 0, 0)
            print("RGB LED: Test completed")
            
        except Exception as e:
            print(f"RGB LED: FAIL - {e}")
            self.test_results['rgb_led_ok'] = False
            
    def test_sd_card(self):
        """
        SD카드의 파일시스템 기능 테스트
        파일 생성→쓰기→읽기→검증→삭제의 전체 과정으로 완전한 기능 확인
        """
        if not self.test_results['sd_ok']:
            return
            
        try:
            # ========== 파일 쓰기 테스트 ==========
            # with 문을 사용하여 파일을 안전하게 열고 자동으로 닫기
            with open('/sd/test.txt', 'w') as f:
                f.write('Pico2 W Test')    # 테스트 문자열 쓰기
                
            # ========== 파일 읽기 테스트 ==========
            with open('/sd/test.txt', 'r') as f:
                content = f.read()         # 파일 내용 전체 읽기
                
            # ========== 내용 검증 ==========
            # 쓴 내용이 올바르게 읽혔는지 확인
            if 'Pico2 W' in content:
                print("SD Card: Read/Write test passed")
            else:
                print("SD Card: Read/Write test failed")
                self.test_results['sd_ok'] = False
                
            # ========== 정리 작업 ==========
            # 테스트 파일 삭제하여 SD카드에 불필요한 파일이 남지 않도록 함
            uos.remove('/sd/test.txt')
            
        except Exception as e:
            print(f"SD Card: FAIL - {e}")
            self.test_results['sd_ok'] = False
            
    def check_button(self):
        """
        버튼 입력을 감지하고 디바운싱 처리를 수행하는 메서드
        기계적 접촉으로 인한 노이즈를 소프트웨어적으로 필터링
        """
        # 현재 시간을 밀리초 단위로 읽기
        current_time = time.ticks_ms()
        
        # 버튼이 눌렸을 때 (풀업 저항으로 인해 LOW = 눌림)
        if not self.button.value():
            # ========== 디바운싱 처리 ==========
            # 마지막 입력으로부터 설정된 지연 시간이 지났는지 확인
            if time.ticks_diff(current_time, self.last_button_time) > DEBOUNCE_DELAY:
                
                # 버튼 테스트 완료 표시
                self.test_results['button_ok'] = True
                
                # 페이지 번호를 순환적으로 증가 (0→1→2→3→0...)
                self.current_page = (self.current_page + 1) % TOTAL_PAGES
                
                # ========== 버튼 입력 피드백 제공 ==========
                # 사용자에게 입력이 인식되었음을 알려주는 시각/청각 피드백
                
                # 부저가 정상 작동하면 확인음 재생
                if self.test_results['buzzer_ok']:
                    self.play_tone(1000, 100)
                    
                # RGB LED가 정상 작동하면 흰색 깜빡임 표시
                if self.test_results['rgb_led_ok']:
                    self.set_rgb_color(255, 255, 255)  # 흰색 켜기
                    time.sleep_ms(100)                 # 100ms 유지
                    self.set_rgb_color(0, 0, 0)        # 끄기
                    
                # 디바운싱을 위해 현재 시간 기록
                self.last_button_time = current_time
                print(f"Button pressed - Page: {self.current_page + 1}")
                
    def update_display(self):
        """
        OLED 디스플레이 내용을 500ms 주기로 업데이트하는 메서드
        현재 페이지에 따라 적절한 정보를 화면에 표시
        """
        # OLED 초기화가 실패한 경우 함수 조기 종료
        if not self.test_results['oled_ok']:
            return
            
        current_time = time.ticks_ms()
        
        # ========== 업데이트 주기 제어 ==========
        # 500ms마다 화면을 업데이트하여 적절한 반응성과 성능의 균형 유지
        if time.ticks_diff(current_time, self.last_display_update) > 500:
            
            # 화면을 검은색으로 지우기
            self.oled.fill(0)
            
            # ========== 현재 페이지에 따른 내용 표시 ==========
            if self.current_page == 0:
                self.display_page1()      # 시스템 상태 페이지
            elif self.current_page == 1:
                self.display_page2()      # 센서 데이터 페이지
            elif self.current_page == 2:
                self.display_page3()      # 제어 장치 페이지
            elif self.current_page == 3:
                self.display_page4()      # 실시간 데이터 페이지
                
            # ========== 페이지 번호 표시 ==========
            # 화면 우하단에 현재 페이지 정보 고정 표시
            # x=96, y=48로 조정하여 텍스트가 화면을 벗어나지 않도록 함
            page_text = f"P{self.current_page + 1}/{TOTAL_PAGES}"
            self.oled.text(page_text, 96, 48)
            
            # 화면에 실제 출력
            self.oled.show()
            
            # 업데이트 시간 기록
            self.last_display_update = current_time
            
    def display_page1(self):
        """
        페이지 1: 시스템 전체 상태 요약 표시
        모든 하드웨어 컴포넌트의 초기화 및 기본 동작 상태를 한눈에 확인
        """
        # 페이지 제목 표시
        self.oled.text("== Pico2 W Status ==", 0, 0)
        
        # ========== 상태 항목들을 리스트로 정리 ==========
        # 튜플을 사용하여 컴포넌트명과 상태를 쌍으로 관리
        status_items = [
            ("OLED", self.test_results['oled_ok']),
            ("WS2812B", self.test_results['ws2812b_ok']),
            ("SD Card", self.test_results['sd_ok']),
            ("DHT22", self.test_results['dht22_ok']),
            ("Button", self.test_results['button_ok'])
        ]
        
        # ========== 각 상태 항목을 순차 표시 ==========
        for i, (name, status) in enumerate(status_items):
            # 상태에 따라 표시할 텍스트 결정
            # 버튼은 아직 누르지 않았으면 "Press" 표시
            if status:
                status_text = "OK"
            elif name != "Button":
                status_text = "FAIL"
            else:
                status_text = "Press"
                
            # 각 항목을 9픽셀 간격으로 세로 배치하여 페이지 번호와 겹치지 않도록 조정
            self.oled.text(f"{name}: {status_text}", 0, 12 + i * 9)
            
    def display_page2(self):
        """
        페이지 2: 센서 데이터 표시
        DHT22 온습도 센서와 LDR 조도 센서의 실제 측정값을 표시
        """
        self.oled.text("=== Sensors ===", 0, 0)
        
        # ========== DHT22 온습도 데이터 표시 ==========
        if self.test_results['dht22_ok']:
            # 온도를 소수점 1자리까지 표시
            self.oled.text(f"Temp: {self.test_results['temperature']:.1f}C", 0, 12)
            
            # 습도를 소수점 1자리까지 표시
            self.oled.text(f"Humidity: {self.test_results['humidity']:.1f}%", 0, 22)
        else:
            # 센서 오류 시 대체 메시지 표시
            self.oled.text("DHT22: No Data", 0, 12)
            
        # ========== LDR 조도 센서 데이터 표시 ==========
        if self.test_results['ldr_ok']:
            # 16비트 ADC 값(0-65535)을 백분율(0-100%)로 변환
            ldr_percent = (self.test_results['ldr_value'] * 100) // 65535
            self.oled.text(f"LDR: {ldr_percent}%", 0, 32)
        else:
            self.oled.text("LDR: FAIL", 0, 32)
            
    def display_page3(self):
        """
        페이지 3: 제어 장치 상태 표시
        사용자 입력 및 출력 장치들의 상태와 사용법 안내
        """
        self.oled.text("=== Controls ===", 0, 0)
        
        # ========== 트리머 가변저항 값 표시 ==========
        if self.test_results['trimmer_ok']:
            # ADC 값을 백분율로 변환하여 직관적으로 표시
            trim_percent = (self.test_results['trimmer_value'] * 100) // 65535
            self.oled.text(f"Trimmer: {trim_percent}%", 0, 12)
        else:
            self.oled.text("Trimmer: FAIL", 0, 12)
            
        # ========== 부저 상태 표시 ==========
        buzzer_status = "OK" if self.test_results['buzzer_ok'] else "FAIL"
        self.oled.text(f"Buzzer: {buzzer_status}", 0, 22)
        
        # ========== RGB LED 상태 표시 ==========
        rgb_status = "OK" if self.test_results['rgb_led_ok'] else "FAIL"
        self.oled.text(f"RGB LED: {rgb_status}", 0, 32)
        
        # ========== 사용법 안내 ==========
        self.oled.text("Press button to", 0, 40)
        self.oled.text("cycle pages", 0, 50)
        
    def display_page4(self):
        """
        페이지 4: 실시간 데이터 표시
        센서값들을 이 페이지가 표시될 때마다 최신값으로 업데이트하여 표시
        """
        # ========== 실시간 센서 값 업데이트 ==========
        # 페이지가 표시될 때마다 최신 센서 값을 읽어와서 실시간 모니터링 구현
        self.test_ldr()
        self.test_trimmer()
        
        self.oled.text("=== Live Data ===", 0, 0)
        
        # ========== 압축된 형태로 온습도 데이터 표시 ==========
        # 한 줄에 온도와 습도를 모두 표시하여 공간 절약
        temp_hum = f"T:{self.test_results['temperature']:.1f}C H:{self.test_results['humidity']:.0f}%"
        self.oled.text(temp_hum, 0, 12)
        
        # ========== LDR 조도 센서 실시간 백분율 표시 ==========
        ldr_percent = (self.test_results['ldr_value'] * 100) // 65535
        self.oled.text(f"LDR: {ldr_percent}%", 0, 22)
        
        # ========== 트리머 실시간 백분율 표시 ==========
        trim_percent = (self.test_results['trimmer_value'] * 100) // 65535
        self.oled.text(f"Trim: {trim_percent}%", 0, 32)
        
        # ========== 진행 중인 데모 상태 표시 ==========
        self.oled.text("WS2812B: Rainbow", 0, 40)
        
    def set_rgb_color(self, r, g, b):
        """
        RGB LED의 색상을 설정하는 유틸리티 메서드
        0-255 범위의 색상값을 16비트 PWM 값으로 변환하여 정밀한 색상 제어
        """
        # RGB LED 초기화가 실패한 경우 함수 조기 종료
        if not self.test_results['rgb_led_ok']:
            return
            
        # ========== 색상값 스케일링 ==========
        # 0-255 범위를 Pico의 16비트 PWM 범위(0-65535)로 변환
        # 이를 통해 정밀한 밝기 조절과 부드러운 색상 표현 가능
        self.led_r.duty_u16(int((r * 65535) / 255))  # 빨간색 강도 설정
        self.led_g.duty_u16(int((g * 65535) / 255))  # 초록색 강도 설정
        self.led_b.duty_u16(int((b * 65535) / 255))  # 파란색 강도 설정
        
    def play_tone(self, frequency, duration):
        """
        부저로 지정된 주파수의 톤을 지정된 시간 동안 재생하는 메서드
        PWM의 주파수와 듀티 사이클을 조절하여 소리 생성
        """
        # 부저 초기화가 실패한 경우 함수 조기 종료
        if not self.test_results['buzzer_ok']:
            return
            
        try:
            # ========== 톤 재생 ==========
            self.buzzer.freq(frequency)      # PWM 주파수를 톤 주파수로 설정
            self.buzzer.duty_u16(32768)      # 50% 듀티 사이클로 적절한 음량 설정
            time.sleep_ms(duration)         # 지정된 시간 동안 톤 유지
            self.buzzer.duty_u16(0)          # 듀티 사이클을 0으로 하여 소리 끄기
            
        except:
            # 톤 재생 중 오류 발생해도 프로그램이 중단되지 않도록 무시
            pass
            
    def rainbow_demo(self):
        """
        WS2812B LED 스트립에 무지개 패턴을 표시하는 메서드
        HSV 색상 공간을 활용하여 연속적으로 변화하는 무지개 효과 구현
        """
        # WS2812B 초기화가 실패한 경우 함수 조기 종료
        if not self.test_results['ws2812b_ok']:
            return
            
        current_time = time.ticks_ms()
        
        # ========== 150ms 주기로 무지개 패턴 업데이트 ==========
        # 너무 빠르면 눈에 부담을 주고, 너무 느리면 어색해 보임
        if time.ticks_diff(current_time, self.last_rainbow_update) > 150:
            
            # ========== 각 LED에 서로 다른 색상 할당 ==========
            for i in range(NUM_PIXELS):
                # 각 LED마다 36도씩 차이나는 색조(Hue) 계산
                # 360도 / 10개 LED = 36도 간격으로 무지개 스펙트럼 배치
                hue = (self.color_index + i * 36) % 360
                
                # HSV(색조, 채도, 명도)를 RGB로 변환
                r, g, b = self.hsv_to_rgb(hue, 255, 100)
                
                # 각 LED에 계산된 RGB 값 할당
                self.ws2812b[i] = (r, g, b)
                
            # ========== 모든 LED에 색상 적용 ==========
            self.ws2812b.write()
            
            # ========== 다음 프레임을 위한 색상 인덱스 증가 ==========
            # 15도씩 회전하여 무지개가 흘러가는 효과 생성
            self.color_index = (self.color_index + 15) % 360
            
            # 업데이트 시간 기록
            self.last_rainbow_update = current_time
            
    def hsv_to_rgb(self, h, s, v):
        """
        HSV(Hue, Saturation, Value) 색상 공간을 RGB로 변환하는 메서드
        HSV는 색상 조작이 직관적이고, RGB는 LED 제어에 필요한 형태
        """
        # ========== HSV 값 정규화 ==========
        # 채도(S)와 명도(V)를 0.0-1.0 범위로 변환
        s = s / 255.0
        v = v / 255.0
        
        # ========== HSV to RGB 변환 알고리즘 ==========
        # 표준 HSV-RGB 변환 수식 사용
        c = v * s                           # 채도 * 명도
        x = c * (1 - abs((h / 60) % 2 - 1)) # 중간값 계산
        m = v - c                           # 명도 오프셋
        
        # ========== 색조 영역별 RGB 성분 계산 ==========
        # 360도 색조를 6개 영역(60도씩)으로 나누어 처리
        if 0 <= h < 60:         # 빨강→노랑 영역
            r, g, b = c, x, 0
        elif 60 <= h < 120:     # 노랑→초록 영역
            r, g, b = x, c, 0
        elif 120 <= h < 180:    # 초록→청록 영역
            r, g, b = 0, c, x
        elif 180 <= h < 240:    # 청록→파랑 영역
            r, g, b = 0, x, c
        elif 240 <= h < 300:    # 파랑→자홍 영역
            r, g, b = x, 0, c
        else:                   # 자홍→빨강 영역 (300-360도)
            r, g, b = c, 0, x
            
        # ========== 최종 RGB 값 계산 및 반환 ==========
        # 0.0-1.0 범위를 0-255 범위로 변환하고 정수형으로 변환
        return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
        
    def run(self):
        """
        메인 실행 루프: 프로그램의 핵심 동작을 관리하는 메서드
        초기 테스트 후 무한 루프에서 사용자 인터페이스와 데모를 실행
        """
        # ========== 초기 테스트 실행 ==========
        # 시스템 안정화를 위해 2초 대기
        time.sleep(2)
        
        # 모든 하드웨어 컴포넌트에 대한 종합 테스트 수행
        self.run_all_tests()
        
        # 사용자에게 프로그램 시작과 사용법 안내
        print("Starting main loop...")
        print("Press the button to cycle through pages!")
        
        # ========== 메인 무한 루프 ==========
        while True:
            try:
                # ========== 핵심 기능들을 순차 실행 ==========
                self.check_button()      # 버튼 입력 감지 및 페이지 전환
                self.update_display()    # OLED 화면 내용 업데이트
                
                # WS2812B가 정상 작동하는 경우에만 무지개 데모 실행
                if self.test_results['ws2812b_ok']:
                    self.rainbow_demo()
                    
                # ========== CPU 사용률 조절 ==========
                # 50ms 지연으로 적절한 반응성과 효율성의 균형 유지
                time.sleep_ms(50)
                
            except KeyboardInterrupt:
                # Ctrl+C로 프로그램 종료 시 우아한 종료 처리
                print("\nProgram stopped by user")
                break
                
            except Exception as e:
                # 예상치 못한 오류 발생 시 에러 출력하고 1초 대기 후 계속 진행
                print(f"Error in main loop: {e}")
                time.sleep(1)


# ========== 메인 실행 부분 ==========
# 스크립트가 직접 실행될 때만 메인 코드 실행 (모듈 import 시에는 실행 안됨)
if __name__ == "__main__":
    try:
        # ========== ComponentTest 객체 생성 및 실행 ==========
        component_test = ComponentTest()  # 클래스 인스턴스 생성 (자동으로 __init__ 호출)
        component_test.run()              # 메인 실행 루프 시작
        
    except Exception as e:
        # 프로그램 시작 자체가 실패한 경우 에러 메시지 출력
        print(f"Failed to start component test: {e}")
        
    finally:
        # ========== 프로그램 종료 시 정리 작업 ==========
        # 예외 발생 여부와 관계없이 항상 실행되는 정리 코드
        print("Cleaning up...")
        
        try:
            # ========== 모든 출력 장치를 안전한 상태로 설정 ==========
            component_test.set_rgb_color(0, 0, 0)      # RGB LED 끄기
            component_test.ws2812b.fill((0, 0, 0))     # WS2812B 모든 LED 끄기
            component_test.ws2812b.write()             # LED 상태 적용
            component_test.buzzer.duty_u16(0)          # 부저 끄기
            
        except:
            # 정리 작업 중 오류 발생해도 무시 (프로그램이 이미 종료 중이므로)

            pass
