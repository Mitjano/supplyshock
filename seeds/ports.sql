-- Seed data: ~50 major world commodity and container ports
-- Safe to re-run: uses ON CONFLICT DO NOTHING on wpi_number

INSERT INTO ports (wpi_number, name, country_code, latitude, longitude, region, harbor_type, max_vessel_size, commodities, annual_throughput_mt, is_major, is_chokepoint)
VALUES

-- ============================================================
-- OIL PORTS
-- ============================================================
(62590, 'Ras Tanura',        'SA', 26.6441,  50.1532, 'Middle East',   'Coastal',   'VLCC',      ARRAY['crude oil','refined products'],           350.00, TRUE,  FALSE),
(62270, 'Jebel Ali',         'AE', 25.0174,  55.0272, 'Middle East',   'Coastal',   'VLCC',      ARRAY['crude oil','containers','general cargo'],  180.00, TRUE,  FALSE),
(62280, 'Fujairah',          'AE', 25.1164,  56.3360, 'Middle East',   'Coastal',   'VLCC',      ARRAY['crude oil','refined products','bunkering'],130.00, TRUE,  FALSE),
(62540, 'Yanbu',             'SA', 24.0895,  38.0618, 'Middle East',   'Coastal',   'VLCC',      ARRAY['crude oil','refined products'],           120.00, TRUE,  FALSE),
(63100, 'Basra Oil Terminal','IQ', 29.6900,  48.8144, 'Middle East',   'Offshore',  'VLCC',      ARRAY['crude oil'],                              200.00, TRUE,  FALSE),
(63290, 'Kharg Island',      'IR', 29.2333,  50.3167, 'Middle East',   'Offshore',  'VLCC',      ARRAY['crude oil'],                              190.00, TRUE,  FALSE),
(62010, 'Novorossiysk',      'RU', 44.7167,  37.7833, 'Black Sea',     'Coastal',   'VLCC',      ARRAY['crude oil','grain','metals'],              155.00, TRUE,  FALSE),

-- ============================================================
-- LNG PORTS
-- ============================================================
(62510, 'Ras Laffan',        'QA', 25.9100,  51.5300, 'Middle East',   'Coastal',   'VLCC',      ARRAY['LNG','condensate'],                       110.00, TRUE,  FALSE),
(13620, 'Sabine Pass',       'US', 29.7303, -93.8700, 'North America', 'River',     'PANAMAX',   ARRAY['LNG','petrochemicals'],                    45.00, TRUE,  FALSE),
(55830, 'Gladstone',         'AU',-23.8489, 151.2789, 'Oceania',       'Coastal',   'PANAMAX',   ARRAY['LNG','coal','alumina'],                    80.00, TRUE,  FALSE),

-- ============================================================
-- COAL PORTS
-- ============================================================
(55820, 'Newcastle',         'AU',-32.9283, 151.7817, 'Oceania',       'Coastal',   'CAPESIZE',  ARRAY['coal'],                                   165.00, TRUE,  FALSE),
(47690, 'Richards Bay',      'ZA',-28.7830,  32.0380, 'Africa',        'Coastal',   'CAPESIZE',  ARRAY['coal','chrome','magnetite'],                92.00, TRUE,  FALSE),
(59000, 'Qinhuangdao',      'CN', 39.9354, 119.6048, 'Asia',          'Coastal',   'CAPESIZE',  ARRAY['coal'],                                   245.00, TRUE,  FALSE),
(55690, 'Hay Point',         'AU',-21.2750, 149.2883, 'Oceania',       'Coastal',   'CAPESIZE',  ARRAY['coal'],                                   110.00, TRUE,  FALSE),

-- ============================================================
-- IRON ORE PORTS
-- ============================================================
(55620, 'Port Hedland',      'AU',-20.3100, 118.5761, 'Oceania',       'Coastal',   'VLCC',      ARRAY['iron ore','manganese','salt'],             575.00, TRUE,  FALSE),
(55600, 'Dampier',           'AU',-20.6617, 116.7133, 'Oceania',       'Coastal',   'CAPESIZE',  ARRAY['iron ore','LNG','salt'],                   195.00, TRUE,  FALSE),
(14450, 'Tubarao (Vitoria)', 'BR',-20.2856, -40.2456, 'South America', 'Coastal',   'VLCC',      ARRAY['iron ore','steel','coal'],                 120.00, TRUE,  FALSE),

-- ============================================================
-- COPPER PORTS
-- ============================================================
(15160, 'Antofagasta',       'CL',-23.6509, -70.3975, 'South America', 'Coastal',   'PANAMAX',   ARRAY['copper','lithium','molybdenum'],            12.00, TRUE,  FALSE),
(15370, 'Callao',            'PE',-12.0464, -77.1425, 'South America', 'Coastal',   'PANAMAX',   ARRAY['copper','zinc','containers','fishmeal'],    38.00, TRUE,  FALSE),

-- ============================================================
-- GRAIN PORTS
-- ============================================================
(13060, 'New Orleans',       'US', 29.9340, -90.0530, 'North America', 'River',     'PANAMAX',   ARRAY['grain','soybeans','coal','petrochemicals'], 95.00, TRUE,  FALSE),
(14200, 'Santos',            'BR',-23.9608, -46.3336, 'South America', 'Coastal',   'PANAMAX',   ARRAY['grain','soybeans','sugar','coffee','containers'], 145.00, TRUE, FALSE),
(49780, 'Odessa',            'UA', 46.4846,  30.7326, 'Black Sea',     'Coastal',   'PANAMAX',   ARRAY['grain','sunflower oil','metals'],           25.00, TRUE,  FALSE),
(41250, 'Rouen',             'FR', 49.4431,   1.0993, 'Europe',        'River',     'HANDYMAX',  ARRAY['grain','refined products','fertilizer'],     22.00, TRUE,  FALSE),
(12270, 'Vancouver',         'CA', 49.2900,-123.1100, 'North America', 'Coastal',   'PANAMAX',   ARRAY['grain','coal','potash','sulphur','containers'], 147.00, TRUE, FALSE),

-- ============================================================
-- CONTAINER / MEGA PORTS
-- ============================================================
(52260, 'Singapore',         'SG',  1.2644, 103.8200, 'Asia',          'Coastal',   'VLCC',      ARRAY['containers','refined products','bunkering','LNG'], 590.00, TRUE, FALSE),
(57050, 'Shanghai',          'CN', 31.3622, 121.5050, 'Asia',          'River',     'VLCC',      ARRAY['containers','steel','vehicles','chemicals'],780.00, TRUE,  FALSE),
(41420, 'Rotterdam',         'NL', 51.9050,   4.4000, 'Europe',        'River',     'VLCC',      ARRAY['containers','crude oil','LNG','iron ore','grain'], 470.00, TRUE, FALSE),
(42230, 'Hamburg',           'DE', 53.5450,   9.9700, 'Europe',        'River',     'PANAMAX',   ARRAY['containers','general cargo'],              130.00, TRUE,  FALSE),
(12710, 'Los Angeles',       'US', 33.7405,-118.2720, 'North America', 'Coastal',   'PANAMAX',   ARRAY['containers','crude oil','vehicles'],       195.00, TRUE,  FALSE),
(12720, 'Long Beach',        'US', 33.7540,-118.2140, 'North America', 'Coastal',   'PANAMAX',   ARRAY['containers','crude oil'],                  185.00, TRUE,  FALSE),
(58900, 'Busan',             'KR', 35.0796, 129.0756, 'Asia',          'Coastal',   'VLCC',      ARRAY['containers','vehicles','steel'],           360.00, TRUE,  FALSE),
(57060, 'Shenzhen (Yantian)','CN', 22.5650, 114.2850, 'Asia',          'Coastal',   'VLCC',      ARRAY['containers','electronics'],                280.00, TRUE,  FALSE),
(41570, 'Antwerp',           'BE', 51.2300,   4.4000, 'Europe',        'River',     'PANAMAX',   ARRAY['containers','chemicals','vehicles'],       240.00, TRUE,  FALSE),
(52350, 'Tanjung Pelepas',   'MY',  1.3625, 103.5500, 'Asia',          'Coastal',   'VLCC',      ARRAY['containers','palm oil'],                   110.00, TRUE,  FALSE),

-- ============================================================
-- GENERAL / MULTI-PURPOSE PORTS
-- ============================================================
(47590, 'Durban',            'ZA',-29.8683,  31.0292, 'Africa',        'Coastal',   'PANAMAX',   ARRAY['containers','coal','chrome','vehicles'],   100.00, TRUE,  FALSE),
(53040, 'JNPT (Nhava Sheva)','IN', 18.9490,  72.9510, 'Asia',         'Coastal',   'PANAMAX',   ARRAY['containers','general cargo','chemicals'],   80.00, TRUE,  FALSE),
(48600, 'Piraeus',           'GR', 37.9475,  23.6372, 'Europe',        'Coastal',   'PANAMAX',   ARRAY['containers','vehicles','general cargo'],    55.00, TRUE,  FALSE),
(40770, 'Algeciras',         'ES', 36.1300,  -5.4400, 'Europe',        'Coastal',   'VLCC',      ARRAY['containers','crude oil','bunkering'],      110.00, TRUE,  FALSE),
(51060, 'Colombo',           'LK',  6.9497,  79.8428, 'Asia',          'Coastal',   'PANAMAX',   ARRAY['containers','tea','rubber'],                72.00, TRUE,  FALSE),
(52330, 'Port Klang',        'MY',  2.9983, 101.3928, 'Asia',          'Coastal',   'PANAMAX',   ARRAY['containers','palm oil','rubber'],          130.00, TRUE,  FALSE),
(52420, 'Laem Chabang',      'TH', 13.0837, 100.8831, 'Asia',         'Coastal',   'PANAMAX',   ARRAY['containers','vehicles','electronics'],      88.00, TRUE,  FALSE),

-- ============================================================
-- ADDITIONAL STRATEGIC PORTS
-- ============================================================
(57400, 'Dalian',            'CN', 38.9200, 121.6500, 'Asia',          'Coastal',   'VLCC',      ARRAY['crude oil','iron ore','containers','grain'],330.00, TRUE,  FALSE),
(57100, 'Ningbo-Zhoushan',   'CN', 29.8683, 121.8900, 'Asia',         'Coastal',   'VLCC',      ARRAY['crude oil','iron ore','containers','coal'],1200.00, TRUE,  FALSE),
(57310, 'Qingdao',           'CN', 36.0671, 120.3826, 'Asia',          'Coastal',   'VLCC',      ARRAY['crude oil','iron ore','containers','coal'], 600.00, TRUE,  FALSE),
(57530, 'Tianjin',           'CN', 38.9867, 117.7247, 'Asia',          'Coastal',   'CAPESIZE',  ARRAY['crude oil','iron ore','coal','containers'], 510.00, TRUE,  FALSE),
(56800, 'Kaohsiung',         'TW', 22.6146, 120.2663, 'Asia',         'Coastal',   'PANAMAX',   ARRAY['containers','petrochemicals','steel'],     155.00, TRUE,  FALSE),
(61070, 'Bandar Abbas',      'IR', 27.1865,  56.2808, 'Middle East',   'Coastal',   'PANAMAX',   ARRAY['containers','iron ore','general cargo'],    85.00, TRUE,  FALSE),
(52430, 'Map Ta Phut',       'TH', 12.7184, 101.1568, 'Asia',         'Coastal',   'HANDYMAX',  ARRAY['LNG','petrochemicals','chemicals'],         42.00, TRUE,  FALSE)

ON CONFLICT (wpi_number) DO NOTHING;
