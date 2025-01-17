Junkie Bot — это пользовательский бот для Telegram, созданный на основе Telethon.
В этой версии основное внимание уделено добавлению новых плагинов (модулей), расширяющих функциональность бота и предоставляющих пользователям дополнительные возможности для автоматизации и персонализации их опыта в Telegram.

**Установка Junkie Bot:**

1. **Клонируйте репозиторий:**

   ```bash
   git clone https://github.com/IT-s-Toxic/Junkie.git
   ```

2. **Перейдите в каталог проекта:**

   ```bash
   cd Junkie
   ```

3. **Установите необходимые зависимости:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Настройте переменные окружения:**

   Создайте файл `.env` и укажите в нем необходимые параметры, такие как `API_ID`, `API_HASH` и другие, требуемые для работы бота.

5. **Запустите бота:**

   ```bash
   python main.py
   ```

**Примечание:** Использование пользовательских ботов может противоречить условиям использования Telegram. Рекомендуется соблюдать осторожность и использовать бота ответственно, чтобы избежать возможных последствий.


**Рекомендуется использовать файл `vars.yaml` для хранения различных переменных, что упрощает дальнейшую разработку модулей. Пример структуры файла:**

```yaml
# Список авторизованных пользователей (если требуется для других плагинов)
AUTHORIZED_USERS:
- 123456790
- 98765421

# Конфигурация базы данных MongoDB
mongodb_uri: "mongodb://localhost:27017/"
db_name: "JunkyDB"

# Ollama настройки
ollama_host: "http://127.0.0.1:11434"
summary_model: "llama3"

# ID канала для логирования
logchannel: -100223344556677

```

**Преимущества использования `vars.yaml`:**

- **Централизованное управление переменными:** Все необходимые переменные собраны в одном месте, что облегчает их настройку и модификацию.

- **Упрощенная разработка модулей:** Модули могут легко получать доступ к значениям из `vars.yaml`, что ускоряет процесс разработки и тестирования.

- **Гибкость настройки:** Добавление или изменение переменных в `vars.yaml` не требует внесения изменений в код модулей, что снижает вероятность ошибок.


- **Гибкость настройки:** Добавление или изменение переменных в `vars.yaml` не требует внесения изменений в код модулей, что снижает вероятность ошибок.

При разработке модулей рекомендуется загружать и использовать переменные из `vars.yaml` для обеспечения согласованности и удобства управления конфигурацией. 
