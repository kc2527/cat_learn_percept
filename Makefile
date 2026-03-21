PORT ?= 8000
HOST ?= 127.0.0.1

.PHONY: help serve serve-open

help:
	@echo "Targets:"
	@echo "  make serve            Open launcher and start local server on http://$(HOST):$(PORT)"
	@echo "  make serve-open       Start server and open launcher page"
	@echo ""
	@echo "Variables:"
	@echo "  PORT=<port>           Override port (default: 8000)"
	@echo "  HOST=<host>           Override host (default: 127.0.0.1)"

serve:
	@echo "Opening launcher and serving /Users/mq20185996/Dropbox/cat_learn_percept on http://$(HOST):$(PORT)"
	@echo "Launcher:     http://$(HOST):$(PORT)/launcher.html"
	@echo "Experiment:   http://$(HOST):$(PORT)/index.html"
	@echo "Space viewer: http://$(HOST):$(PORT)/space_viewer.html"
	@open "http://$(HOST):$(PORT)/launcher.html"
	python3 -m http.server $(PORT) --bind $(HOST)

serve-open:
	@echo "Opening launcher and starting local server..."
	@open "http://$(HOST):$(PORT)/launcher.html"
	python3 -m http.server $(PORT) --bind $(HOST)
