def test_server_settings_parsing(monkeypatch):
    monkeypatch.setenv("POWERMEM_SERVER_AUTH_ENABLED", "false")
    monkeypatch.setenv("POWERMEM_SERVER_LOG_FILE", "")
    monkeypatch.setenv("POWERMEM_SERVER_LOG_MAX_SIZE", "2 MB")
    monkeypatch.setenv("POWERMEM_SERVER_LOG_BACKUP_COUNT", "7")
    monkeypatch.setenv("POWERMEM_SERVER_LOG_COMPRESS_BACKUPS", "enabled")
    monkeypatch.setenv("POWERMEM_SERVER_API_KEYS", " a, b ,, c ")
    monkeypatch.setenv(
        "POWERMEM_SERVER_CORS_ORIGINS", "https://a.example, https://b.example"
    )
    monkeypatch.setenv("POWERMEM_SERVER_RELOAD", "enabled")

    from server.config import ServerSettings

    settings = ServerSettings(_env_file=None)

    assert settings.auth_enabled is False
    assert settings.log_file is None
    assert settings.log_max_size == "2 MB"
    assert settings.log_backup_count == 7
    assert settings.log_compress_backups is True
    assert settings.get_api_keys_list() == ["a", "b", "c"]
    assert settings.get_cors_origins_list() == [
        "https://a.example",
        "https://b.example",
    ]
