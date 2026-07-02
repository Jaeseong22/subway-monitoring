import { Station } from '../types';

export const stations: Station[] = [
{
  id: '1001001003',
  name: '연천',
  nameEn: 'Yeoncheon',
  hasTransfer: false,
  transferLines: [],
  description: '1호선의 새로운 북쪽 종착역입니다.',
  landmarks: ['연천군청']
},
{
  id: '1001001002',
  name: '전곡',
  nameEn: 'Jeongok',
  hasTransfer: false,
  transferLines: [],
  description: '연천군의 주요 역입니다.',
  landmarks: ['전곡리 유적']
},
{
  id: '1001001001',
  name: '청산',
  nameEn: 'Cheongsan',
  hasTransfer: false,
  transferLines: [],
  description: '연천군에 위치한 역입니다.',
  landmarks: ['청산면']
},
{
  id: '1001000100',
  name: '소요산',
  nameEn: 'Soyosan',
  hasTransfer: false,
  transferLines: [],
  description: '1호선의 북쪽 종착역 중 하나입니다.',
  landmarks: ['소요산', '자유수호평화박물관']
},
{
  id: '1001000101',
  name: '동두천',
  nameEn: 'Dongducheon',
  hasTransfer: false,
  transferLines: [],
  description: '동두천시의 주요 역입니다.',
  landmarks: ['동두천시청']
},
{
  id: '1001000102',
  name: '보산',
  nameEn: 'Bosan',
  hasTransfer: false,
  transferLines: [],
  description: '미군 부대 인근에 위치한 역입니다.',
  landmarks: ['보산동 관광특구']
},
{
  id: '1001000103',
  name: '동두천중앙',
  nameEn: 'Dongducheon Jungang',
  hasTransfer: false,
  transferLines: [],
  description: '동두천 구도심의 중심 역입니다.',
  landmarks: ['중앙시장']
},
{
  id: '1001000104',
  name: '지행',
  nameEn: 'Jihaeng',
  hasTransfer: false,
  transferLines: [],
  description: '동두천 신시가지의 중심 역입니다.',
  landmarks: ['지행역 상가']
},
{
  id: '1001000105',
  name: '덕정',
  nameEn: 'Deokjeong',
  hasTransfer: false,
  transferLines: [],
  description: '양주시 덕정동에 위치한 역입니다.',
  landmarks: ['서정대학교']
},
{
  id: '1001000106',
  name: '덕계',
  nameEn: 'Deokgye',
  hasTransfer: false,
  transferLines: [],
  description: '양주시 덕계동에 위치한 역입니다.',
  landmarks: ['덕계저수지']
},
{
  id: '1001000107',
  name: '양주',
  nameEn: 'Yangju',
  hasTransfer: false,
  transferLines: [],
  description: '양주시청 인근에 위치한 역입니다.',
  landmarks: ['양주시청']
},
{
  id: '1001000108',
  name: '녹양',
  nameEn: 'Nogyang',
  hasTransfer: false,
  transferLines: [],
  description: '의정부시 녹양동에 위치한 역입니다.',
  landmarks: ['의정부종합운동장']
},
{
  id: '1001000109',
  name: '가능',
  nameEn: 'Ganeung',
  hasTransfer: false,
  transferLines: [],
  description: '구 의정부역으로 불렸던 역입니다.',
  landmarks: ['의정부여고']
},
{
  id: '1001000110',
  name: '의정부',
  nameEn: 'Uijeongbu',
  hasTransfer: false,
  transferLines: [],
  description: '의정부시의 중심 역입니다.',
  landmarks: ['의정부제일시장', '신세계백화점']
},
{
  id: '1001000111',
  name: '회룡',
  nameEn: 'Hoeryong',
  hasTransfer: true,
  transferLines: ['의정부경전철'],
  description: '의정부경전철 환승역입니다.',
  landmarks: ['회룡사']
},
{
  id: '1001000112',
  name: '망월사',
  nameEn: 'Mangwolsa',
  hasTransfer: false,
  transferLines: [],
  description: '신한대학교 인근 역입니다.',
  landmarks: ['신한대학교', '망월사']
},
{
  id: '1001000113',
  name: '도봉산',
  nameEn: 'Dobongsan',
  hasTransfer: true,
  transferLines: ['7호선'],
  description: '도봉산 등산객이 많이 찾는 환승역입니다.',
  landmarks: ['도봉산', '서울창포원']
},
{
  id: '1001000114',
  name: '도봉',
  nameEn: 'Dobong',
  hasTransfer: false,
  transferLines: [],
  description: '도봉구에 위치한 역입니다.',
  landmarks: ['도봉구청']
},
{
  id: '1001000115',
  name: '방학',
  nameEn: 'Banghak',
  hasTransfer: false,
  transferLines: [],
  description: '도봉구청 인근 역입니다.',
  landmarks: ['도봉구청']
},
{
  id: '1001000116',
  name: '창동',
  nameEn: 'Chang-dong',
  hasTransfer: true,
  transferLines: ['4호선'],
  description: '4호선 환승역입니다.',
  landmarks: ['창동문화체육센터']
},
{
  id: '1001000117',
  name: '녹천',
  nameEn: 'Nokcheon',
  hasTransfer: false,
  transferLines: [],
  description: '초안산 인근 역입니다.',
  landmarks: ['초안산생태공원']
},
{
  id: '1001000118',
  name: '월계',
  nameEn: 'Wolgye',
  hasTransfer: false,
  transferLines: [],
  description: '인덕대학교 인근 역입니다.',
  landmarks: ['인덕대학교']
},
{
  id: '1001000119',
  name: '광운대',
  nameEn: 'Kwangwoon Univ.',
  hasTransfer: true,
  transferLines: ['경춘선'],
  description: '경춘선 환승역이자 주요 종착역입니다.',
  landmarks: ['광운대학교']
},
{
  id: '1001000120',
  name: '석계',
  nameEn: 'Seokgye',
  hasTransfer: true,
  transferLines: ['6호선'],
  description: '6호선 환승역입니다.',
  landmarks: ['석계역 문화공원']
},
{
  id: '1001000121',
  name: '신이문',
  nameEn: 'Sinimun',
  hasTransfer: false,
  transferLines: [],
  description: '한국예술종합학교 인근 역입니다.',
  landmarks: ['한국예술종합학교']
},
{
  id: '1001000122',
  name: '외대앞',
  nameEn: 'Hankuk Univ. of Foreign Studies',
  hasTransfer: false,
  transferLines: [],
  description: '한국외국어대학교 인근 역입니다.',
  landmarks: ['한국외국어대학교']
},
{
  id: '1001000123',
  name: '회기',
  nameEn: 'Hoegi',
  hasTransfer: true,
  transferLines: ['경의중앙선', '경춘선'],
  description: '경희대학교 인근 환승역입니다.',
  landmarks: ['경희대학교', '서울시립대학교']
},
{
  id: '1001000124',
  name: '청량리',
  nameEn: 'Cheongnyangni',
  hasTransfer: true,
  transferLines: ['경의중앙선', '경춘선', '수인분당선'],
  description: '서울 동북부의 주요 교통 허브입니다.',
  landmarks: ['청량리시장', '롯데백화점']
},
{
  id: '1001000125',
  name: '제기동',
  nameEn: 'Jegi-dong',
  hasTransfer: false,
  transferLines: [],
  description: '약령시장 인근 역입니다.',
  landmarks: ['서울약령시', '경동시장']
},
{
  id: '1001000126',
  name: '신설동',
  nameEn: 'Sinseol-dong',
  hasTransfer: true,
  transferLines: ['2호선', '우이신설선'],
  description: '3개 노선이 만나는 환승역입니다.',
  landmarks: ['풍물시장']
},
{
  id: '1001000127',
  name: '동묘앞',
  nameEn: 'Dongmyo',
  hasTransfer: true,
  transferLines: ['6호선'],
  description: '구제시장으로 유명한 역입니다.',
  landmarks: ['동묘구제시장', '동관왕묘']
},
{
  id: '1001000128',
  name: '동대문',
  nameEn: 'Dongdaemun',
  hasTransfer: true,
  transferLines: ['4호선'],
  description: '동대문 패션타운 인근 역입니다.',
  landmarks: ['흥인지문', '동대문종합시장']
},
{
  id: '1001000129',
  name: '종로5가',
  nameEn: 'Jongno 5(o)-ga',
  hasTransfer: false,
  transferLines: [],
  description: '광장시장 인근 역입니다.',
  landmarks: ['광장시장', '종묘']
},
{
  id: '1001000130',
  name: '종로3가',
  nameEn: 'Jongno 3(sam)-ga',
  hasTransfer: true,
  transferLines: ['3호선', '5호선'],
  description: '서울 중심부의 주요 환승역입니다.',
  landmarks: ['탑골공원', '익선동']
},
{
  id: '1001000131',
  name: '종각',
  nameEn: 'Jonggak',
  hasTransfer: false,
  transferLines: [],
  description: '보신각 인근 역입니다.',
  landmarks: ['보신각', '청계천']
},
{
  id: '1001000132',
  name: '시청',
  nameEn: 'City Hall',
  hasTransfer: true,
  transferLines: ['2호선'],
  description: '서울시청 인근 환승역입니다.',
  landmarks: ['서울시청', '덕수궁']
},
{
  id: '1001000133',
  name: '서울역',
  nameEn: 'Seoul Station',
  hasTransfer: true,
  transferLines: ['4호선', '경의중앙선', '공항철도'],
  description: '대한민국의 철도 중심지입니다.',
  landmarks: ['서울역', '남대문시장']
},
{
  id: '1001000134',
  name: '남영',
  nameEn: 'Namyeong',
  hasTransfer: false,
  transferLines: [],
  description: '숙명여대 인근 역입니다.',
  landmarks: ['숙명여자대학교']
},
{
  id: '1001000135',
  name: '용산',
  nameEn: 'Yongsan',
  hasTransfer: true,
  transferLines: ['경의중앙선'],
  description: '용산전자상가 및 KTX 정차역입니다.',
  landmarks: ['아이파크몰', '용산전자상가']
},
{
  id: '1001000136',
  name: '노량진',
  nameEn: 'Noryangjin',
  hasTransfer: true,
  transferLines: ['9호선'],
  description: '수산시장 및 학원가 인근 역입니다.',
  landmarks: ['노량진수산시장', '노량진학원가']
},
{
  id: '1001000137',
  name: '대방',
  nameEn: 'Daebang',
  hasTransfer: true,
  transferLines: ['신림선'],
  description: '여의도 인근 역입니다.',
  landmarks: ['여의도샛강생태공원']
},
{
  id: '1001000138',
  name: '신길',
  nameEn: 'Singil',
  hasTransfer: true,
  transferLines: ['5호선'],
  description: '5호선 환승역입니다.',
  landmarks: ['여의도공원']
},
{
  id: '1001000139',
  name: '영등포',
  nameEn: 'Yeongdeungpo',
  hasTransfer: false,
  transferLines: [],
  description: '서울 서남부의 주요 상업지구입니다.',
  landmarks: ['타임스퀘어', '영등포전통시장']
},
{
  id: '1001000140',
  name: '신도림',
  nameEn: 'Sindorim',
  hasTransfer: true,
  transferLines: ['2호선'],
  description: '가장 혼잡한 환승역 중 하나입니다.',
  landmarks: ['디큐브시티']
},
{
  id: '1001000141',
  name: '구로',
  nameEn: 'Guro',
  hasTransfer: false,
  transferLines: [],
  description: '인천행과 수원/천안행이 갈라지는 역입니다.',
  landmarks: ['구로기계공구상가']
},
{
  id: '1001000142',
  name: '구일',
  nameEn: 'Guil',
  hasTransfer: false,
  transferLines: [],
  description: '구로구 구일동에 위치한 역입니다.',
  landmarks: ['구일공원']
},
{
  id: '1001000143',
  name: '개봉',
  nameEn: 'Gaebong',
  hasTransfer: false,
  transferLines: [],
  description: '구로구 개봉동에 위치한 역입니다.',
  landmarks: ['개봉근린공원']
},
{
  id: '1001000144',
  name: '오류동',
  nameEn: 'Oryu-dong',
  hasTransfer: false,
  transferLines: [],
  description: '구로구 오류동에 위치한 역입니다.',
  landmarks: ['항동철길']
},
{
  id: '1001000145',
  name: '온수',
  nameEn: 'Onsu',
  hasTransfer: true,
  transferLines: ['7호선'],
  description: '7호선 환승역입니다.',
  landmarks: ['온수골공원']
},
{
  id: '1001000146',
  name: '역곡',
  nameEn: 'Yeokgok',
  hasTransfer: false,
  transferLines: [],
  description: '부천시 역곡동에 위치한 역입니다.',
  landmarks: ['역곡상업지구']
},
{
  id: '1001000147',
  name: '소사',
  nameEn: 'Sosa',
  hasTransfer: true,
  transferLines: ['서해선'],
  description: '서해선 환승역입니다.',
  landmarks: ['소사역 전통시장']
},
{
  id: '1001000148',
  name: '부천',
  nameEn: 'Bucheon',
  hasTransfer: false,
  transferLines: [],
  description: '부천시의 중심 역입니다.',
  landmarks: ['부천시청', '부천역 로데오거리']
},
{
  id: '1001000149',
  name: '중동',
  nameEn: 'Jung-dong',
  hasTransfer: false,
  transferLines: [],
  description: '부천시 중동 신도시에 위치한 역입니다.',
  landmarks: ['부천중앙공원']
},
{
  id: '1001000150',
  name: '송내',
  nameEn: 'Songnae',
  hasTransfer: false,
  transferLines: [],
  description: '부천시 송내동에 위치한 역입니다.',
  landmarks: ['송내역 상가']
},
{
  id: '1001000151',
  name: '부개',
  nameEn: 'Bugae',
  hasTransfer: false,
  transferLines: [],
  description: '부천시 부개동에 위치한 역입니다.',
  landmarks: ['부개역 상가']
},
{
  id: '1001000152',
  name: '부평',
  nameEn: 'Bupyeong',
  hasTransfer: true,
  transferLines: ['인천1호선'],
  description: '인천 부평의 중심 환승역입니다.',
  landmarks: ['부평지하상가', '부평문화의거리']
},
{
  id: '1001000153',
  name: '백운',
  nameEn: 'Baegun',
  hasTransfer: false,
  transferLines: [],
  description: '인천 부평구에 위치한 역입니다.',
  landmarks: ['백운공원']
},
{
  id: '1001000154',
  name: '동암',
  nameEn: 'Dongam',
  hasTransfer: false,
  transferLines: [],
  description: '인천 부평구 산곡동에 위치한 역입니다.',
  landmarks: ['부평체육관']
},
{
  id: '1001000155',
  name: '간석',
  nameEn: 'Ganseok',
  hasTransfer: false,
  transferLines: [],
  description: '인천 남동구 간석동에 위치한 역입니다.',
  landmarks: ['간석오거리']
},
{
  id: '1001000156',
  name: '주안',
  nameEn: 'Juan',
  hasTransfer: true,
  transferLines: ['인천2호선'],
  description: '인천2호선 환승역입니다.',
  landmarks: ['주안역 상가', '신기시장']
},
{
  id: '1001000157',
  name: '도화',
  nameEn: 'Dohwa',
  hasTransfer: false,
  transferLines: [],
  description: '인천 미추홀구에 위치한 역입니다.',
  landmarks: ['도화공원']
},
{
  id: '1001000158',
  name: '제물포',
  nameEn: 'Jemulpo',
  hasTransfer: false,
  transferLines: [],
  description: '인천 개항장 인근 역입니다.',
  landmarks: ['인천상륙작전기념관']
},
{
  id: '1001000159',
  name: '도원',
  nameEn: 'Dowon',
  hasTransfer: false,
  transferLines: [],
  description: '인천 미추홀구에 위치한 역입니다.',
  landmarks: ['수봉공원']
},
{
  id: '1001000160',
  name: '동인천',
  nameEn: 'Dong-incheon',
  hasTransfer: false,
  transferLines: [],
  description: '인천 구도심의 중심 역입니다.',
  landmarks: ['신포국제시장', '차이나타운']
},
{
  id: '1001000161',
  name: '인천',
  nameEn: 'Incheon',
  hasTransfer: false,
  transferLines: [],
  description: '1호선 인천 방면 종착역입니다.',
  landmarks: ['월미도', '인천항']
},
// ── 경부선 (천안/신창 방면) ── 구로에서 분기
{
  id: '1001080142',
  name: '가산디지털단지',
  nameEn: 'Gasan Digital Complex',
  hasTransfer: true,
  transferLines: ['7호선'],
  description: '서울디지털산업단지의 중심 환승역입니다.',
  landmarks: ['마리오아울렛', '가산디지털단지']
},
{
  id: '1001080143',
  name: '독산',
  nameEn: 'Doksan',
  hasTransfer: false,
  transferLines: [],
  description: '금천구 독산동에 위치한 역입니다.',
  landmarks: ['독산역 상가']
},
{
  id: '1001080144',
  name: '금천구청',
  nameEn: 'Geumcheon-gu Office',
  hasTransfer: false,
  transferLines: [],
  description: '금천구청 인근 역입니다.',
  landmarks: ['금천구청', '시흥대로']
},
{
  id: '1001075410',
  name: '광명',
  nameEn: 'Gwangmyeong',
  hasTransfer: false,
  transferLines: [],
  description: '광명시에 위치한 역입니다.',
  landmarks: ['광명시장']
},
{
  id: '1001080145',
  name: '석수',
  nameEn: 'Seoksu',
  hasTransfer: false,
  transferLines: [],
  description: '안양시 만안구에 위치한 역입니다.',
  landmarks: ['석수시장']
},
{
  id: '1001080146',
  name: '관악',
  nameEn: 'Gwanak',
  hasTransfer: false,
  transferLines: [],
  description: '안양시 만안구에 위치한 역입니다.',
  landmarks: ['관악역 상가']
},
{
  id: '1001080147',
  name: '안양',
  nameEn: 'Anyang',
  hasTransfer: false,
  transferLines: [],
  description: '안양시의 중심 역입니다.',
  landmarks: ['안양중앙시장', '안양역 상가']
},
{
  id: '1001080148',
  name: '명학',
  nameEn: 'Myeonghak',
  hasTransfer: false,
  transferLines: [],
  description: '안양시 동안구에 위치한 역입니다.',
  landmarks: ['명학역 상가']
},
{
  id: '1001080149',
  name: '금정',
  nameEn: 'Geumjeong',
  hasTransfer: true,
  transferLines: ['4호선'],
  description: '4호선 환승역입니다.',
  landmarks: ['금정역 환승센터']
},
{
  id: '1001080150',
  name: '군포',
  nameEn: 'Gunpo',
  hasTransfer: false,
  transferLines: [],
  description: '군포시의 중심 역입니다.',
  landmarks: ['군포시청']
},
{
  id: '1001080151',
  name: '당정',
  nameEn: 'Dangjeong',
  hasTransfer: false,
  transferLines: [],
  description: '군포시 당정동에 위치한 역입니다.',
  landmarks: ['당정역 상가']
},
{
  id: '1001080152',
  name: '의왕',
  nameEn: 'Uiwang',
  hasTransfer: false,
  transferLines: [],
  description: '의왕시의 중심 역입니다.',
  landmarks: ['의왕시청', '철도박물관']
},
{
  id: '1001080153',
  name: '성균관대',
  nameEn: 'Sungkyunkwan Univ.',
  hasTransfer: false,
  transferLines: [],
  description: '성균관대학교 자연과학캠퍼스 인근 역입니다.',
  landmarks: ['성균관대학교']
},
{
  id: '1001080154',
  name: '화서',
  nameEn: 'Hwaseo',
  hasTransfer: false,
  transferLines: [],
  description: '수원시 팔달구에 위치한 역입니다.',
  landmarks: ['화서역 상가']
},
{
  id: '1001080155',
  name: '수원',
  nameEn: 'Suwon',
  hasTransfer: true,
  transferLines: ['수인분당선'],
  description: '수원시의 중심 환승역입니다.',
  landmarks: ['수원역 로데오거리', '수원화성']
},
{
  id: '1001080156',
  name: '세류',
  nameEn: 'Seryu',
  hasTransfer: false,
  transferLines: [],
  description: '수원시 권선구에 위치한 역입니다.',
  landmarks: ['세류역 상가']
},
{
  id: '1001080157',
  name: '병점',
  nameEn: 'Byeongjeom',
  hasTransfer: false,
  transferLines: [],
  description: '화성시 병점동에 위치한 역입니다.',
  landmarks: ['병점역 상가']
},
{
  id: '1001801571',
  name: '서동탄',
  nameEn: 'Seodongtan',
  hasTransfer: false,
  transferLines: [],
  description: '동탄신도시 서쪽에 위치한 역입니다.',
  landmarks: ['동탄신도시']
},
{
  id: '1001080158',
  name: '세마',
  nameEn: 'Sema',
  hasTransfer: false,
  transferLines: [],
  description: '오산시 세마동에 위치한 역입니다.',
  landmarks: ['세마역 상가']
},
{
  id: '1001080159',
  name: '오산대',
  nameEn: 'Osan College',
  hasTransfer: false,
  transferLines: [],
  description: '오산대학교 인근 역입니다.',
  landmarks: ['오산대학교']
},
{
  id: '1001080160',
  name: '오산',
  nameEn: 'Osan',
  hasTransfer: false,
  transferLines: [],
  description: '오산시의 중심 역입니다.',
  landmarks: ['오산시청']
},
{
  id: '1001080161',
  name: '진위',
  nameEn: 'Jinwi',
  hasTransfer: false,
  transferLines: [],
  description: '평택시 진위면에 위치한 역입니다.',
  landmarks: ['진위역 상가']
},
{
  id: '1001080162',
  name: '송탄',
  nameEn: 'Songtan',
  hasTransfer: false,
  transferLines: [],
  description: '평택시 송탄 지역의 중심 역입니다.',
  landmarks: ['송탄관광특구']
},
{
  id: '1001080163',
  name: '서정리',
  nameEn: 'Seojeongni',
  hasTransfer: false,
  transferLines: [],
  description: '평택시 서정동에 위치한 역입니다.',
  landmarks: ['서정리역 상가']
},
{
  id: '1001080164',
  name: '지제',
  nameEn: 'Jije',
  hasTransfer: true,
  transferLines: ['SRT'],
  description: 'SRT 평택지제역 환승역입니다.',
  landmarks: ['평택지제역']
},
{
  id: '1001080165',
  name: '평택',
  nameEn: 'Pyeongtaek',
  hasTransfer: false,
  transferLines: [],
  description: '평택시의 중심 역입니다.',
  landmarks: ['평택역 상가', '평택시청']
},
{
  id: '1001080166',
  name: '성환',
  nameEn: 'Seonghwan',
  hasTransfer: false,
  transferLines: [],
  description: '천안시 서북구 성환읍에 위치한 역입니다.',
  landmarks: ['성환역 상가']
},
{
  id: '1001080167',
  name: '직산',
  nameEn: 'Jiksan',
  hasTransfer: false,
  transferLines: [],
  description: '천안시 서북구 직산읍에 위치한 역입니다.',
  landmarks: ['직산역 상가']
},
{
  id: '1001080168',
  name: '두정',
  nameEn: 'Dujeong',
  hasTransfer: false,
  transferLines: [],
  description: '천안시 서북구에 위치한 역입니다.',
  landmarks: ['두정역 상가']
},
{
  id: '1001080169',
  name: '천안',
  nameEn: 'Cheonan',
  hasTransfer: false,
  transferLines: [],
  description: '천안시의 중심 역입니다.',
  landmarks: ['천안역 광장', '천안종합터미널']
},
{
  id: '1001080170',
  name: '봉명',
  nameEn: 'Bongmyeong',
  hasTransfer: false,
  transferLines: [],
  description: '천안시 서북구 봉명동에 위치한 역입니다.',
  landmarks: ['봉명역 상가']
},
{
  id: '1001080171',
  name: '쌍용',
  nameEn: 'Ssangyong',
  hasTransfer: false,
  transferLines: [],
  description: '나사렛대학교 인근 역입니다.',
  landmarks: ['나사렛대학교']
},
{
  id: '1001080172',
  name: '아산',
  nameEn: 'Asan',
  hasTransfer: false,
  transferLines: [],
  description: '아산시에 위치한 역입니다.',
  landmarks: ['아산시청']
},
{
  id: '1001080174',
  name: '배방',
  nameEn: 'Baebang',
  hasTransfer: false,
  transferLines: [],
  description: '아산시 배방읍에 위치한 역입니다.',
  landmarks: ['배방역 상가']
},
{
  id: '1001080175',
  name: '온양온천',
  nameEn: 'Onyang Oncheon',
  hasTransfer: false,
  transferLines: [],
  description: '온양온천 관광지 인근 역입니다.',
  landmarks: ['온양온천', '온양민속박물관']
},
{
  id: '1001080176',
  name: '신창',
  nameEn: 'Sinchang',
  hasTransfer: false,
  transferLines: [],
  description: '1호선 천안/신창 방면 종착역입니다.',
  landmarks: ['신창역']
}];
