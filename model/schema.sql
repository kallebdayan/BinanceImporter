-- ========================================
-- ESTRUTURA DO BANCO DE DADOS PARA BINANCE
-- ========================================

-- Tabela principal para armazenar todas as moedas da Binance
CREATE TABLE coins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL,
    base_asset VARCHAR(20) NOT NULL,
    base_asset_precision INT NOT NULL,
    quote_asset VARCHAR(20) NOT NULL,
    quote_precision INT NOT NULL,
    quote_asset_precision INT NOT NULL,
    base_commission_precision INT NOT NULL,
    quote_commission_precision INT NOT NULL,
    order_types JSON NOT NULL,
    iceberg_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    oco_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    quote_order_qty_market_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    allow_trailing_stop BOOLEAN NOT NULL DEFAULT FALSE,
    cancel_replace_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    is_spot_trading_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    is_margin_trading_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    filters JSON NOT NULL,
    permissions JSON NOT NULL,
    default_self_trade_prevention_mode VARCHAR(20),
    allowed_self_trade_prevention_modes JSON,
    -- Campos para análise técnica
    min_price DECIMAL(20,8) DEFAULT NULL,
    max_price DECIMAL(20,8) DEFAULT NULL,
    tick_size DECIMAL(20,8) DEFAULT NULL,
    multiplier_up DECIMAL(10,4) DEFAULT NULL,
    multiplier_down DECIMAL(10,4) DEFAULT NULL,
    min_qty DECIMAL(20,8) DEFAULT NULL,
    max_qty DECIMAL(20,8) DEFAULT NULL,
    step_size DECIMAL(20,8) DEFAULT NULL,
    min_notional DECIMAL(20,8) DEFAULT NULL,
    apply_to_market BOOLEAN DEFAULT FALSE,
    max_num_orders INT DEFAULT NULL,
    max_num_algo_orders INT DEFAULT NULL,
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Índices para performance
    INDEX idx_symbol (symbol),
    INDEX idx_status (status),
    INDEX idx_quote_asset (quote_asset),
    INDEX idx_base_asset (base_asset),
    INDEX idx_trading_allowed (is_spot_trading_allowed),
    INDEX idx_status_quote (status, quote_asset)
);

-- Tabela específica para tokens USDT ativos para trading
CREATE TABLE tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    coin_id INT NOT NULL,
    symbol VARCHAR(50) NOT NULL UNIQUE,
    base_asset VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    is_spot_trading_allowed BOOLEAN NOT NULL,
    is_margin_trading_allowed BOOLEAN NOT NULL,
    quote_asset VARCHAR(20) NOT NULL DEFAULT 'USDT',
    -- Dados essenciais para análise
    min_price DECIMAL(20,8),
    max_price DECIMAL(20,8),
    tick_size DECIMAL(20,8),
    min_qty DECIMAL(20,8),
    max_qty DECIMAL(20,8),
    step_size DECIMAL(20,8),
    min_notional DECIMAL(20,8),
    -- Permissões e características
    iceberg_allowed BOOLEAN DEFAULT FALSE,
    oco_allowed BOOLEAN DEFAULT FALSE,
    allow_trailing_stop BOOLEAN DEFAULT FALSE,
    cancel_replace_allowed BOOLEAN DEFAULT FALSE,
    order_types JSON,
    permissions JSON,
    filters JSON,
    -- Timestamps
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Constraints
    FOREIGN KEY (coin_id) REFERENCES coins(id) ON DELETE CASCADE,
    
    -- Índices
    INDEX idx_symbol (symbol),
    INDEX idx_base_asset (base_asset),
    INDEX idx_status (status),
    INDEX idx_trading_allowed (is_spot_trading_allowed)
);

-- ========================================
-- TRIGGER PARA SINCRONIZAÇÃO AUTOMÁTICA
-- ========================================

DELIMITER $$

CREATE TRIGGER sync_usdt_tokens_insert
    AFTER INSERT ON coins
    FOR EACH ROW
BEGIN
    -- Inserir apenas se for USDT, status TRADING e spot trading allowed
    IF NEW.quote_asset = 'USDT' 
       AND NEW.status = 'TRADING' 
       AND NEW.is_spot_trading_allowed = TRUE THEN
        
        INSERT INTO tokens (
            coin_id,
            symbol,
            base_asset,
            status,
            is_spot_trading_allowed,
            is_margin_trading_allowed,
            quote_asset,
            min_price,
            max_price,
            tick_size,
            min_qty,
            max_qty,
            step_size,
            min_notional,
            iceberg_allowed,
            oco_allowed,
            allow_trailing_stop,
            cancel_replace_allowed,
            order_types,
            permissions,
            filters
        ) VALUES (
            NEW.id,
            NEW.symbol,
            NEW.base_asset,
            NEW.status,
            NEW.is_spot_trading_allowed,
            NEW.is_margin_trading_allowed,
            NEW.quote_asset,
            NEW.min_price,
            NEW.max_price,
            NEW.tick_size,
            NEW.min_qty,
            NEW.max_qty,
            NEW.step_size,
            NEW.min_notional,
            NEW.iceberg_allowed,
            NEW.oco_allowed,
            NEW.allow_trailing_stop,
            NEW.cancel_replace_allowed,
            NEW.order_types,
            NEW.permissions,
            NEW.filters
        );
    END IF;
END$$

CREATE TRIGGER sync_usdt_tokens_update
    AFTER UPDATE ON coins
    FOR EACH ROW
BEGIN
    -- Se era USDT e continua sendo, atualiza
    IF OLD.quote_asset = 'USDT' AND NEW.quote_asset = 'USDT' 
       AND NEW.status = 'TRADING' 
       AND NEW.is_spot_trading_allowed = TRUE THEN
        
        UPDATE tokens SET
            symbol = NEW.symbol,
            base_asset = NEW.base_asset,
            status = NEW.status,
            is_spot_trading_allowed = NEW.is_spot_trading_allowed,
            is_margin_trading_allowed = NEW.is_margin_trading_allowed,
            min_price = NEW.min_price,
            max_price = NEW.max_price,
            tick_size = NEW.tick_size,
            min_qty = NEW.min_qty,
            max_qty = NEW.max_qty,
            step_size = NEW.step_size,
            min_notional = NEW.min_notional,
            iceberg_allowed = NEW.iceberg_allowed,
            oco_allowed = NEW.oco_allowed,
            allow_trailing_stop = NEW.allow_trailing_stop,
            cancel_replace_allowed = NEW.cancel_replace_allowed,
            order_types = NEW.order_types,
            permissions = NEW.permissions,
            filters = NEW.filters,
            updated_at = CURRENT_TIMESTAMP
        WHERE coin_id = NEW.id;
        
    -- Se era USDT mas não atende mais aos critérios, remove
    ELSEIF OLD.quote_asset = 'USDT' AND 
           (NEW.quote_asset != 'USDT' OR 
            NEW.status != 'TRADING' OR 
            NEW.is_spot_trading_allowed = FALSE) THEN
        
        DELETE FROM tokens WHERE coin_id = NEW.id;
        
    -- Se não era USDT mas agora atende aos critérios, insere
    ELSEIF OLD.quote_asset != 'USDT' AND 
           NEW.quote_asset = 'USDT' AND 
           NEW.status = 'TRADING' AND 
           NEW.is_spot_trading_allowed = TRUE THEN
        
        INSERT INTO tokens (
            coin_id,
            symbol,
            base_asset,
            status,
            is_spot_trading_allowed,
            is_margin_trading_allowed,
            quote_asset,
            min_price,
            max_price,
            tick_size,
            min_qty,
            max_qty,
            step_size,
            min_notional,
            iceberg_allowed,
            oco_allowed,
            allow_trailing_stop,
            cancel_replace_allowed,
            order_types,
            permissions,
            filters
        ) VALUES (
            NEW.id,
            NEW.symbol,
            NEW.base_asset,
            NEW.status,
            NEW.is_spot_trading_allowed,
            NEW.is_margin_trading_allowed,
            NEW.quote_asset,
            NEW.min_price,
            NEW.max_price,
            NEW.tick_size,
            NEW.min_qty,
            NEW.max_qty,
            NEW.step_size,
            NEW.min_notional,
            NEW.iceberg_allowed,
            NEW.oco_allowed,
            NEW.allow_trailing_stop,
            NEW.cancel_replace_allowed,
            NEW.order_types,
            NEW.permissions,
            NEW.filters
        );
    END IF;
END$$

CREATE TRIGGER sync_usdt_tokens_delete
    AFTER DELETE ON coins
    FOR EACH ROW
BEGIN
    -- Remove da tabela tokens se existir
    DELETE FROM tokens WHERE coin_id = OLD.id;
END$$

DELIMITER ;

-- ========================================
-- PROCEDURE PARA SINCRONIZAÇÃO INICIAL
-- ========================================

DELIMITER $$

CREATE PROCEDURE SyncExistingUSDTTokens()
BEGIN
    -- Limpa a tabela tokens
    DELETE FROM tokens;
    
    -- Insere todos os tokens USDT ativos
    INSERT INTO tokens (
        coin_id,
        symbol,
        base_asset,
        status,
        is_spot_trading_allowed,
        is_margin_trading_allowed,
        quote_asset,
        min_price,
        max_price,
        tick_size,
        min_qty,
        max_qty,
        step_size,
        min_notional,
        iceberg_allowed,
        oco_allowed,
        allow_trailing_stop,
        cancel_replace_allowed,
        order_types,
        permissions,
        filters
    )
    SELECT 
        id,
        symbol,
        base_asset,
        status,
        is_spot_trading_allowed,
        is_margin_trading_allowed,
        quote_asset,
        min_price,
        max_price,
        tick_size,
        min_qty,
        max_qty,
        step_size,
        min_notional,
        iceberg_allowed,
        oco_allowed,
        allow_trailing_stop,
        cancel_replace_allowed,
        order_types,
        permissions,
        filters
    FROM coins 
    WHERE quote_asset = 'USDT' 
      AND status = 'TRADING' 
      AND is_spot_trading_allowed = TRUE;
      
    SELECT CONCAT('Sincronizados ', ROW_COUNT(), ' tokens USDT') AS resultado;
END$$

DELIMITER ;

-- ========================================
-- VIEWS ÚTEIS PARA ANÁLISE
-- ========================================

-- View para tokens ativos com informações resumidas
CREATE VIEW active_usdt_tokens AS
SELECT 
    t.symbol,
    t.base_asset,
    t.min_price,
    t.max_price,
    t.tick_size,
    t.min_qty,
    t.max_qty,
    t.step_size,
    t.min_notional,
    t.iceberg_allowed,
    t.oco_allowed,
    t.allow_trailing_stop,
    t.is_margin_trading_allowed,
    t.updated_at
FROM tokens t
WHERE t.status = 'TRADING'
ORDER BY t.symbol;

-- View para estatísticas gerais
CREATE VIEW tokens_stats AS
SELECT 
    COUNT(*) as total_tokens,
    COUNT(CASE WHEN is_margin_trading_allowed = TRUE THEN 1 END) as margin_enabled,
    COUNT(CASE WHEN iceberg_allowed = TRUE THEN 1 END) as iceberg_enabled,
    COUNT(CASE WHEN oco_allowed = TRUE THEN 1 END) as oco_enabled,
    COUNT(CASE WHEN allow_trailing_stop = TRUE THEN 1 END) as trailing_stop_enabled,
    AVG(min_notional) as avg_min_notional,
    MIN(min_notional) as min_notional_value,
    MAX(min_notional) as max_notional_value
FROM tokens
WHERE status = 'TRADING';

-- ========================================
-- COMANDOS PARA EXECUÇÃO INICIAL
-- ========================================

-- Executar após inserir dados na tabela coins:
-- CALL SyncExistingUSDTTokens();

-- Para verificar os resultados:
-- SELECT * FROM active_usdt_tokens LIMIT 10;
-- SELECT * FROM tokens_stats;

-- Tabela para armazenar dados de candles
CREATE TABLE `candles` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `symbol` varchar(50) NOT NULL,
  `interval_type` varchar(10) NOT NULL,
  `open_time` bigint(20) NOT NULL,
  `close_time` bigint(20) NOT NULL,
  `open_price` decimal(20,8) NOT NULL,
  `high_price` decimal(20,8) NOT NULL,
  `low_price` decimal(20,8) NOT NULL,
  `close_price` decimal(20,8) NOT NULL,
  `volume` decimal(20,8) NOT NULL,
  `quote_asset_volume` decimal(20,8) NOT NULL,
  `number_of_trades` int(11) NOT NULL,
  `taker_buy_base_asset_volume` decimal(20,8) NOT NULL,
  `taker_buy_quote_asset_volume` decimal(20,8) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_candle` (`symbol`, `interval_type`, `open_time`),
  KEY `idx_symbol` (`symbol`),
  KEY `idx_interval` (`interval_type`),
  KEY `idx_open_time` (`open_time`),
  KEY `idx_symbol_interval_time` (`symbol`, `interval_type`, `open_time`),
  CONSTRAINT `candles_ibfk_1` FOREIGN KEY (`symbol`) REFERENCES `tokens` (`symbol`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Tabela para controle de coleta de dados
CREATE TABLE `collection_control` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `symbol` varchar(50) NOT NULL,
  `interval_type` varchar(10) NOT NULL,
  `last_collected_time` bigint(20) NOT NULL,
  `status` enum('active','paused','error') NOT NULL DEFAULT 'active',
  `error_count` int(11) NOT NULL DEFAULT 0,
  `last_error` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_symbol_interval` (`symbol`, `interval_type`),
  KEY `idx_symbol` (`symbol`),
  KEY `idx_status` (`status`),
  CONSTRAINT `collection_control_ibfk_1` FOREIGN KEY (`symbol`) REFERENCES `tokens` (`symbol`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Tabela para log de coletas
CREATE TABLE `collection_logs` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `symbol` varchar(50) NOT NULL,
  `interval_type` varchar(10) NOT NULL,
  `collection_type` enum('single','continuous') NOT NULL,
  `start_time` bigint(20) DEFAULT NULL,
  `end_time` bigint(20) DEFAULT NULL,
  `records_collected` int(11) NOT NULL DEFAULT 0,
  `status` enum('success','error','partial') NOT NULL,
  `error_message` text DEFAULT NULL,
  `execution_time` decimal(10,3) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_symbol` (`symbol`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- View para tokens ativos com trading habilitado
CREATE VIEW `active_trading_tokens` AS
SELECT 
  t.id,
  t.symbol,
  t.base_asset,
  t.quote_asset,
  t.status,
  t.is_spot_trading_allowed,
  t.is_margin_trading_allowed,
  t.min_price,
  t.max_price,
  t.tick_size,
  t.min_qty,
  t.max_qty,
  t.step_size,
  t.min_notional
FROM tokens t
WHERE t.status = 'TRADING' 
  AND t.is_spot_trading_allowed = 1
ORDER BY t.symbol;

-- View para últimos candles coletados por símbolo
CREATE VIEW `latest_candles` AS
SELECT 
  c.symbol,
  c.interval_type,
  c.open_time,
  c.close_time,
  c.open_price,
  c.high_price,
  c.low_price,
  c.close_price,
  c.volume,
  c.quote_asset_volume,
  c.number_of_trades,
  c.created_at,
  ROW_NUMBER() OVER (PARTITION BY c.symbol, c.interval_type ORDER BY c.open_time DESC) as rn
FROM candles c;

-- View para estatísticas de coleta por símbolo
CREATE VIEW `collection_stats` AS
SELECT 
  c.symbol,
  c.interval_type,
  COUNT(*) as total_candles,
  MIN(c.open_time) as first_candle_time,
  MAX(c.open_time) as last_candle_time,
  AVG(c.volume) as avg_volume,
  AVG(c.number_of_trades) as avg_trades,
  cc.status as collection_status,
  cc.last_collected_time,
  cc.error_count,
  cc.last_error
FROM candles c
LEFT JOIN collection_control cc ON c.symbol = cc.symbol AND c.interval_type = cc.interval_type
GROUP BY c.symbol, c.interval_type, cc.status, cc.last_collected_time, cc.error_count, cc.last_error;

-- View para indicadores básicos (últimos 24 candles - 24h para intervalo 1h)
CREATE VIEW `basic_indicators` AS
SELECT 
  c.symbol,
  c.interval_type,
  AVG(c.close_price) as avg_close_24,
  MIN(c.low_price) as min_low_24,
  MAX(c.high_price) as max_high_24,
  SUM(c.volume) as total_volume_24,
  COUNT(*) as candles_count,
  (MAX(c.close_price) - MIN(c.close_price)) / MIN(c.close_price) * 100 as price_range_percent,
  STDDEV(c.close_price) as price_volatility
FROM candles c
WHERE c.open_time >= (UNIX_TIMESTAMP(NOW() - INTERVAL 24 HOUR) * 1000)
GROUP BY c.symbol, c.interval_type
HAVING candles_count >= 20;

-- View para análise de gaps de dados
CREATE VIEW `data_gaps` AS
SELECT 
  c1.symbol,
  c1.interval_type,
  c1.close_time as gap_start,
  c2.open_time as gap_end,
  (c2.open_time - c1.close_time) as gap_duration_ms,
  CASE 
    WHEN c1.interval_type = '1m' THEN (c2.open_time - c1.close_time) / 60000
    WHEN c1.interval_type = '5m' THEN (c2.open_time - c1.close_time) / 300000
    WHEN c1.interval_type = '15m' THEN (c2.open_time - c1.close_time) / 900000
    WHEN c1.interval_type = '1h' THEN (c2.open_time - c1.close_time) / 3600000
    WHEN c1.interval_type = '4h' THEN (c2.open_time - c1.close_time) / 14400000
    WHEN c1.interval_type = '1d' THEN (c2.open_time - c1.close_time) / 86400000
    ELSE (c2.open_time - c1.close_time) / 60000
  END as gap_intervals
FROM candles c1
JOIN candles c2 ON c1.symbol = c2.symbol 
  AND c1.interval_type = c2.interval_type
  AND c2.open_time = (
    SELECT MIN(open_time) 
    FROM candles c3 
    WHERE c3.symbol = c1.symbol 
      AND c3.interval_type = c1.interval_type 
      AND c3.open_time > c1.close_time
  )
WHERE (c2.open_time - c1.close_time) > (
  CASE 
    WHEN c1.interval_type = '1m' THEN 60000
    WHEN c1.interval_type = '5m' THEN 300000
    WHEN c1.interval_type = '15m' THEN 900000
    WHEN c1.interval_type = '1h' THEN 3600000
    WHEN c1.interval_type = '4h' THEN 14400000
    WHEN c1.interval_type = '1d' THEN 86400000
    ELSE 60000
  END * 1.1  -- 10% de tolerância
)
ORDER BY c1.symbol, c1.interval_type, gap_start;
