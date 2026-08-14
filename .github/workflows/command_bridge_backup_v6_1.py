name: Kabar Saham V6.1 - Command Bridge

on:
  workflow_dispatch:
    inputs:
      mode:
        description: 'Poll Telegram command atau test bridge'
        required: true
        default: 'poll'
        type: choice
        options:
          - poll
          - test

permissions:
  contents: write

# Same concurrency key as V6.0 Auto Alert.
# This prevents state commits from overlapping with the scanner workflow.
concurrency:
  group: kabar-saham-v6-scanner
  cancel-in-progress: false

jobs:
  command-bridge:
    runs-on: ubuntu-latest
    timeout-minutes: 12

    steps:
      - name: Checkout repository
        uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Resolve mode
        id: mode
        shell: bash
        run: |
          echo "value=${{ inputs.mode }}" >> "$GITHUB_OUTPUT"

      - name: Telegram command probe
        id: bridge
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_IDS: ${{ secrets.TELEGRAM_CHAT_IDS }}

          V61_COMMAND_STATE_PATH: ${{ github.workspace }}/state/command_state.json
          V61_PENDING_COMMANDS_PATH: ${{ runner.temp }}/pending_commands_v61.json
          V61_COMMAND_MAX_UPDATES: '20'
          V61_TELEGRAM_TIMEOUT_SECONDS: '20'
        run: |
          if [ "${{ steps.mode.outputs.value }}" = "test" ]; then
            python command_bridge.py \
              --mode test \
              --github-output "$GITHUB_OUTPUT"
          else
            python command_bridge.py \
              --mode probe \
              --github-output "$GITHUB_OUTPUT"
          fi

      - name: Install full intelligence dependencies
        if: steps.mode.outputs.value == 'poll' && steps.bridge.outputs.has_commands == 'true'
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt

      - name: Execute Telegram commands
        if: steps.mode.outputs.value == 'poll' && steps.bridge.outputs.has_commands == 'true'
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_IDS: ${{ secrets.TELEGRAM_CHAT_IDS }}

          CONFIG_PATH: ${{ github.workspace }}/config.json
          DB_PATH: ${{ runner.temp }}/runtime_v61.db

          V61_COMMAND_STATE_PATH: ${{ github.workspace }}/state/command_state.json
          V61_PENDING_COMMANDS_PATH: ${{ runner.temp }}/pending_commands_v61.json

          NEWS_POLL_MINUTES: '10'
          RECENT_DAYS: '30'
          AUTO_ALERT_HOURS: '48'
          INDONESIA_PRIORITY: '1'
          AUTO_ALERT_MIN_PRIORITY: 'MEDIUM'

          MARKET_DATA_ENABLED: '1'
          MARKET_CACHE_MINUTES: '15'
          DECISION_LOTS: '1'
          MARKET_ENRICH_LIMIT: '5'

          DEEP_EXTRACTION_ENABLED: '1'
          DEEP_EXTRACT_LIMIT: '3'
          ARTICLE_CACHE_MINUTES: '60'
          ARTICLE_TIMEOUT_SECONDS: '15'
          MAX_ARTICLE_CHARS: '30000'

          SOURCE_RESOLVER_ENABLED: '1'
          RESOLVER_MAX_CANDIDATES: '8'
          RESOLVER_SEARCH_FALLBACK: '1'
          RESOLVER_CACHE_MINUTES: '180'
          RESOLVER_TITLE_MIN_SCORE: '35'

          GOOGLE_DECODER_ENABLED: '1'
          GOOGLE_DECODER_BATCH_ENABLED: '1'
          GOOGLE_DECODER_TIMEOUT_SECONDS: '12'
          GOOGLE_DECODER_MAX_TOKEN_CHARS: '4096'
          GOOGLE_DECODER_CACHE_MINUTES: '180'

          DECODER_DEBUG_ENABLED: '0'
          DECODER_MAX_RESPONSE_CHARS: '250000'
          DECODER_MAX_URL_CANDIDATES: '20'
          DECODER_MAX_NESTED_JSON_DEPTH: '5'

          DYNAMIC_PROTOCOL_ENABLED: '1'
          DYNAMIC_PARAMS_TIMEOUT_SECONDS: '12'
          DYNAMIC_PARAMS_CACHE_MINUTES: '180'
          DYNAMIC_PROTOCOL_FALLBACK_STATIC: '1'
          DYNAMIC_PARAMS_HTML_MAX_CHARS: '500000'

          PUBLISHER_DIRECT_ENABLED: '1'
          PUBLISHER_DIRECT_MIN_SCORE: '70'
          PUBLISHER_DIRECT_CACHE_MINUTES: '180'
          PUBLISHER_DIRECT_TIMEOUT_SECONDS: '12'
          PUBLISHER_DIRECT_MAX_CANDIDATES: '12'
          PUBLISHER_INTERNAL_SEARCH_ENABLED: '1'
          PUBLISHER_PUBLIC_SEARCH_ENABLED: '1'

        run: |
          python command_bridge.py --mode execute

      - name: Persist Command Bridge state
        if: steps.mode.outputs.value == 'poll'
        shell: bash
        run: |
          git config user.name "kabar-saham-v6-bot"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

          git add state/command_state.json

          if git diff --cached --quiet; then
            echo "Command state unchanged; nothing to commit."
            exit 0
          fi

          git commit -m "chore(state): update V6.1 command bridge [skip ci]"

          for attempt in 1 2 3; do
            echo "Push attempt $attempt..."
            if git pull --rebase origin "${GITHUB_REF_NAME}" && \
               git push origin "HEAD:${GITHUB_REF_NAME}"; then
              echo "Command state persisted."
              exit 0
            fi

            git rebase --abort 2>/dev/null || true
            sleep $((attempt * 2))
          done

          echo "Failed to persist command state after 3 attempts."
          exit 1
