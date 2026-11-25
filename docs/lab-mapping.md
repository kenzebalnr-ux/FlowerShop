# Зертханалық талаптардың орындалу картасы

Жобаның негізгі тақырыбы — FlowerShop гүлдерге онлайн тапсырыс беру жүйесі. 1–7 жұмыстар пайдаланушы берген DOCX әдістемесіне, 8-жұмыс [берілген қосымша тапсырмаға](https://chatgpt.com/s/t_6af4005ed7f88191a5fabf3cf1cedc50) негізделеді.

| № | Талап | Жобадағы дәлел |
|---|---|---|
| 1 | ER, кемінде 3 байланысты мән | `docs/images/er-diagram.png`, 6 SQLModel кестесі |
| 1 | Python, API/БД/UI, Git | `backend/`, `frontend/`, `.gitignore`, README |
| 2 | ORM PK/FK, Relationship | `backend/models.py` |
| 2 | Seed және БД құру | `backend/db.py`, `backend/seed.py`; 4 санат, 12 тауар, 3 үлгі пайдаланушы/тапсырыс |
| 3 | GET list/detail, POST201 | `/api/products`, `/api/products/{id}` |
| 3 | Сессия Depends, Swagger | `backend/db.py`, `backend/main.py`, `/docs` |
| 4 | PATCH/PUT/DELETE | Әкімші тауар маршруттары; 404, 204 |
| 4 | Іздеу/баға сүзгісі | `search`, `min_price`, `max_price`, `category_id`, `sort` |
| 5 | Streamlit, HTTP, table/form | `frontend/streamlit_app.py` |
| 5 | Іздеу/қосу/жою | Streamlit каталогы, әкімші формалары |
| 6 | Екі Dockerfile, Compose | `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` |
| 6 | Қызмет атауы арқылы байланыс | `BACKEND_URL=http://backend:8000` |
| 6 | Деректі сақтау | `flowershop_data:/data` named volume |
| 7 | Кемінде 2–3 API тест | `tests/test_integration.py` және `tests/test_security.py` |
| 7 | README, қорғау | README және `docs/labs/01–07` |
| 8 | Компоненттер, әрқайсысына ≥2 ықтимал қате | `docs/labs/08-testing-report.md` архитектура кестесі |
| 8 | ≥5 интеграция сценарийі, DB rollback | `tests/test_integration.py` |
| 8 | ≥10 қалыпты/шекаралық/теріс тест | pytest жиынтығы, нақты нәтиже есепте |
| 8 | Қауіпсіздік: пароль, рөл, логтар | `tests/test_security.py` |
| 8 | 5/20/50/100 жүктеме, CPU/RAM | `tests/locustfile.py`, `scripts/run_load.py`, `docs/results/load/` |
| 8 | CI сәтті/қате/түзету дәлелі | `.github/workflows/tests.yml`; run URL және күйі есепте |
| 8 | Нәтиже, диаграмма, қорытынды | `docs/labs/08-testing-report.md`, `docs/results/` |

## Талаптарды бейімдеу

- Әдістемедегі мысал `app/` құрылымы модульдердің міндетін көрсетеді. Мұнда backend және frontend жеке бумаларда орналасады; сәйкестік README-де түсіндірілген.
- Репозиторий атауы пайдаланушының нақты тапсырмасына сәйкес `FlowerShop` болып сақталды.
- Бастапқы әдістемедегі әдепкі 422 орнына 8-зертханадағы формат қатесі келісіміне сәйкес кіріс валидациясы бірыңғай 400 қайтарады; бұл шешім 3-зертхана есебінде көрсетілген.
- Өнімнің бағасы оң бүтін теңгемен сақталады. Ақша есептеуде бөлшек floating point қатесі болмайды.
- `authsession` уақытша қауіпсіздік кестесіне seed токендері енгізілмейді; жазбалар тек сәтті login кезінде жасалады.
- Ұсынылған «жеті апта» Git тарихы қолдан жасалмайды; коммиттер нақты орындалған күнмен сақталады.
- Сайт пен тест кодының бар болуы сыртқы GitHub CI немесе Docker іске қосылғанының дәлелі емес. Орындалған тексерулер мен орындалмаған қадамдар 8-зертхана есебінде бөлінеді.
