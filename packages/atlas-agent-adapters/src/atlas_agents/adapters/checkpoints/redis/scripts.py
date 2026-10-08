"""Static Lua programs used as Redis checkpoint linearization points."""

SAVE_SCRIPT = r"""
if redis.call('EXISTS', KEYS[1]) == 1 then
  return {0, 'exists'}
end
redis.call('HSET', KEYS[1],
  'state', 'active',
  'schema_version', ARGV[1],
  'checkpoint_version', ARGV[2],
  'execution_id', ARGV[3],
  'agent_id', ARGV[4],
  'tenant_id', ARGV[5],
  'revision', '1',
  'payload', ARGV[6],
  'payload_digest', ARGV[7],
  'expires_at_ms', ARGV[8],
  'retention_until_ms', ARGV[9],
  'retention_policy_version', ARGV[10])
if tonumber(ARGV[9]) > 0 then
  redis.call('PEXPIREAT', KEYS[1], ARGV[9])
end
return {1, 'saved'}
"""

READ_SCRIPT = r"""
local function now_ms()
  local now = redis.call('TIME')
  return tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
end
if redis.call('EXISTS', KEYS[1]) == 0 then
  return {0, 'missing'}
end
local schema = redis.call('HGET', KEYS[1], 'schema_version')
if schema ~= ARGV[1] then
  return {-1, schema or 'missing'}
end
local state = redis.call('HGET', KEYS[1], 'state')
if state ~= 'active' then
  return {0, state or 'invalid'}
end
local expires_at = tonumber(redis.call('HGET', KEYS[1], 'expires_at_ms') or '0')
if expires_at > 0 and now_ms() >= expires_at then
  redis.call('HSET', KEYS[1], 'state', 'expired')
  redis.call('HDEL', KEYS[1], 'payload', 'payload_digest')
  return {0, 'expired'}
end
local payload = redis.call('HGET', KEYS[1], 'payload')
if not payload then
  return {-2, 'corrupted'}
end
return {1, payload,
  redis.call('HGET', KEYS[1], 'revision'),
  redis.call('HGET', KEYS[1], 'execution_id'),
  redis.call('HGET', KEYS[1], 'agent_id'),
  redis.call('HGET', KEYS[1], 'tenant_id'),
  redis.call('HGET', KEYS[1], 'payload_digest')}
"""

COMPARE_AND_SWAP_SCRIPT = r"""
local function now_ms()
  local now = redis.call('TIME')
  return tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
end
if redis.call('EXISTS', KEYS[1]) == 0 then
  return {0, 'missing'}
end
if redis.call('HGET', KEYS[1], 'schema_version') ~= ARGV[1] then
  return {-1, redis.call('HGET', KEYS[1], 'schema_version') or 'missing'}
end
if redis.call('HGET', KEYS[1], 'state') ~= 'active' then
  return {0, redis.call('HGET', KEYS[1], 'state') or 'invalid'}
end
local expires_at = tonumber(redis.call('HGET', KEYS[1], 'expires_at_ms') or '0')
if expires_at > 0 and now_ms() >= expires_at then
  redis.call('HSET', KEYS[1], 'state', 'expired')
  redis.call('HDEL', KEYS[1], 'payload', 'payload_digest')
  return {0, 'expired'}
end
local actual_revision = tonumber(redis.call('HGET', KEYS[1], 'revision') or '0')
if actual_revision ~= tonumber(ARGV[2]) then
  return {-3, tostring(actual_revision)}
end
if redis.call('HGET', KEYS[1], 'execution_id') ~= ARGV[3]
  or redis.call('HGET', KEYS[1], 'agent_id') ~= ARGV[4]
  or redis.call('HGET', KEYS[1], 'tenant_id') ~= ARGV[5] then
  return {-4, 'identity'}
end
local next_revision = actual_revision + 1
redis.call('HSET', KEYS[1],
  'checkpoint_version', ARGV[6],
  'revision', tostring(next_revision),
  'payload', ARGV[7],
  'payload_digest', ARGV[8],
  'expires_at_ms', ARGV[9],
  'retention_until_ms', ARGV[10],
  'retention_policy_version', ARGV[11])
if tonumber(ARGV[10]) > 0 then
  redis.call('PEXPIREAT', KEYS[1], ARGV[10])
else
  redis.call('PERSIST', KEYS[1])
end
return {1, ARGV[7], tostring(next_revision)}
"""

CONSUME_SCRIPT = r"""
local function now_ms()
  local now = redis.call('TIME')
  return tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
end
if redis.call('EXISTS', KEYS[1]) == 0 then
  return {0, 'missing'}
end
if redis.call('HGET', KEYS[1], 'schema_version') ~= ARGV[1] then
  return {-1, redis.call('HGET', KEYS[1], 'schema_version') or 'missing'}
end
local state = redis.call('HGET', KEYS[1], 'state')
if state ~= 'active' then
  return {0, state or 'invalid'}
end
local expires_at = tonumber(redis.call('HGET', KEYS[1], 'expires_at_ms') or '0')
local current_time = now_ms()
if expires_at > 0 and current_time >= expires_at then
  redis.call('HSET', KEYS[1], 'state', 'expired')
  redis.call('HDEL', KEYS[1], 'payload', 'payload_digest')
  return {0, 'expired'}
end
local actual_revision = redis.call('HGET', KEYS[1], 'revision')
local actual_digest = redis.call('HGET', KEYS[1], 'payload_digest')
if ARGV[2] ~= '' and actual_revision ~= ARGV[2] then
  return {-3, actual_revision or '0'}
end
if ARGV[3] ~= '' and actual_digest ~= ARGV[3] then
  return {-3, actual_revision or '0'}
end
local payload = redis.call('HGET', KEYS[1], 'payload')
if not payload then
  return {-2, 'corrupted'}
end
local retention_until = current_time + tonumber(ARGV[4])
redis.call('HSET', KEYS[1],
  'state', 'consumed',
  'consumed_at_ms', tostring(current_time),
  'retention_until_ms', tostring(retention_until),
  'consume_operation_id', ARGV[5])
redis.call('HDEL', KEYS[1], 'payload', 'payload_digest')
redis.call('PEXPIREAT', KEYS[1], retention_until)
return {1, payload}
"""

RECONCILE_SCRIPT = r"""
if redis.call('EXISTS', KEYS[1]) == 0 then
  return {0, 'missing'}
end
local state = redis.call('HGET', KEYS[1], 'state')
local operation_id = redis.call('HGET', KEYS[1], 'consume_operation_id')
if state == 'consumed' and operation_id == ARGV[1] then
  return {1, 'applied'}
end
return {0, state or 'invalid'}
"""

ACQUIRE_LEASE_SCRIPT = r"""
local function now_ms()
  local now = redis.call('TIME')
  return tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
end
if redis.call('EXISTS', KEYS[1]) == 0 then
  return {0, 'missing'}
end
if redis.call('HGET', KEYS[1], 'schema_version') ~= ARGV[1] then
  return {-1, redis.call('HGET', KEYS[1], 'schema_version') or 'missing'}
end
if redis.call('HGET', KEYS[1], 'state') ~= 'active' then
  return {0, redis.call('HGET', KEYS[1], 'state') or 'invalid'}
end
local current_time = now_ms()
local checkpoint_expiration = tonumber(
  redis.call('HGET', KEYS[1], 'expires_at_ms') or '0')
if checkpoint_expiration > 0 and current_time >= checkpoint_expiration then
  redis.call('HSET', KEYS[1], 'state', 'expired')
  redis.call('HDEL', KEYS[1], 'payload', 'payload_digest', 'lease_owner_id',
    'lease_acquired_at_ms', 'lease_expires_at_ms')
  return {0, 'expired'}
end
local lease_owner = redis.call('HGET', KEYS[1], 'lease_owner_id') or ''
local lease_expiration = tonumber(
  redis.call('HGET', KEYS[1], 'lease_expires_at_ms') or '0')
if lease_owner ~= '' and lease_expiration > current_time then
  return {-5, 'conflict'}
end
local generation = tonumber(
  redis.call('HGET', KEYS[1], 'lease_fencing_token') or '0') + 1
local expires_at = current_time + tonumber(ARGV[3])
redis.call('HSET', KEYS[1],
  'lease_owner_id', ARGV[2],
  'lease_fencing_token', tostring(generation),
  'lease_acquired_at_ms', tostring(current_time),
  'lease_expires_at_ms', tostring(expires_at))
return {1, redis.call('HGET', KEYS[1], 'execution_id'), ARGV[2],
  tostring(generation), tostring(current_time), tostring(expires_at)}
"""

RENEW_LEASE_SCRIPT = r"""
local function now_ms()
  local now = redis.call('TIME')
  return tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
end
if redis.call('EXISTS', KEYS[1]) == 0 then
  return {0, 'missing'}
end
local current_time = now_ms()
local expiration = tonumber(redis.call('HGET', KEYS[1], 'lease_expires_at_ms') or '0')
if redis.call('HGET', KEYS[1], 'state') ~= 'active'
  or redis.call('HGET', KEYS[1], 'execution_id') ~= ARGV[1]
  or redis.call('HGET', KEYS[1], 'lease_owner_id') ~= ARGV[2]
  or redis.call('HGET', KEYS[1], 'lease_fencing_token') ~= ARGV[3]
  or expiration <= current_time then
  return {-6, 'lost'}
end
local requested_expiration = current_time + tonumber(ARGV[4])
local next_expiration = math.max(expiration, requested_expiration)
redis.call('HSET', KEYS[1], 'lease_expires_at_ms', tostring(next_expiration))
return {1, ARGV[1], ARGV[2], ARGV[3],
  redis.call('HGET', KEYS[1], 'lease_acquired_at_ms'), tostring(next_expiration)}
"""

RELEASE_LEASE_SCRIPT = r"""
local function now_ms()
  local now = redis.call('TIME')
  return tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
end
if redis.call('EXISTS', KEYS[1]) == 0 then
  return {0, 'missing'}
end
if redis.call('HGET', KEYS[1], 'state') ~= 'active'
  or redis.call('HGET', KEYS[1], 'execution_id') ~= ARGV[1]
  or redis.call('HGET', KEYS[1], 'lease_owner_id') ~= ARGV[2]
  or redis.call('HGET', KEYS[1], 'lease_fencing_token') ~= ARGV[3]
  or tonumber(redis.call(
    'HGET', KEYS[1], 'lease_expires_at_ms') or '0') <= now_ms() then
  return {-6, 'lost'}
end
redis.call('HDEL', KEYS[1], 'lease_owner_id',
  'lease_acquired_at_ms', 'lease_expires_at_ms')
return {1, 'released'}
"""

COMPARE_AND_SWAP_LEASED_SCRIPT = r"""
local function now_ms()
  local now = redis.call('TIME')
  return tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
end
if redis.call('EXISTS', KEYS[1]) == 0 then return {0, 'missing'} end
if redis.call('HGET', KEYS[1], 'schema_version') ~= ARGV[1] then
  return {-1, redis.call('HGET', KEYS[1], 'schema_version') or 'missing'}
end
if redis.call('HGET', KEYS[1], 'state') ~= 'active' then
  return {0, redis.call('HGET', KEYS[1], 'state') or 'invalid'}
end
local current_time = now_ms()
local expires_at = tonumber(redis.call('HGET', KEYS[1], 'expires_at_ms') or '0')
if expires_at > 0 and current_time >= expires_at then return {0, 'expired'} end
local actual_revision = tonumber(redis.call('HGET', KEYS[1], 'revision') or '0')
if actual_revision ~= tonumber(ARGV[2]) then return {-3, tostring(actual_revision)} end
if redis.call('HGET', KEYS[1], 'execution_id') ~= ARGV[3]
  or redis.call('HGET', KEYS[1], 'agent_id') ~= ARGV[4]
  or redis.call('HGET', KEYS[1], 'tenant_id') ~= ARGV[5] then
  return {-4, 'identity'}
end
if redis.call('HGET', KEYS[1], 'lease_owner_id') ~= ARGV[12]
  or redis.call('HGET', KEYS[1], 'lease_fencing_token') ~= ARGV[13]
  or tonumber(redis.call(
    'HGET', KEYS[1], 'lease_expires_at_ms') or '0') <= current_time then
  return {-6, 'lost'}
end
local next_revision = actual_revision + 1
redis.call('HSET', KEYS[1], 'checkpoint_version', ARGV[6],
  'revision', tostring(next_revision), 'payload', ARGV[7],
  'payload_digest', ARGV[8], 'expires_at_ms', ARGV[9],
  'retention_until_ms', ARGV[10], 'retention_policy_version', ARGV[11])
if tonumber(ARGV[10]) > 0 then redis.call('PEXPIREAT', KEYS[1], ARGV[10])
else redis.call('PERSIST', KEYS[1]) end
return {1, ARGV[7], tostring(next_revision)}
"""

CONSUME_LEASED_SCRIPT = r"""
local function now_ms()
  local now = redis.call('TIME')
  return tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
end
if redis.call('EXISTS', KEYS[1]) == 0 then return {0, 'missing'} end
if redis.call('HGET', KEYS[1], 'schema_version') ~= ARGV[1] then
  return {-1, redis.call('HGET', KEYS[1], 'schema_version') or 'missing'}
end
local state = redis.call('HGET', KEYS[1], 'state')
if state ~= 'active' then
  if state == 'consumed'
    and redis.call('HGET', KEYS[1], 'consume_operation_id') == ARGV[6] then
    return {2, 'already_applied'}
  end
  return {0, state or 'invalid'}
end
local current_time = now_ms()
local expires_at = tonumber(redis.call('HGET', KEYS[1], 'expires_at_ms') or '0')
if expires_at > 0 and current_time >= expires_at then return {0, 'expired'} end
local actual_revision = redis.call('HGET', KEYS[1], 'revision')
if actual_revision ~= ARGV[2]
  or redis.call('HGET', KEYS[1], 'payload_digest') ~= ARGV[3] then
  return {-3, actual_revision or '0'}
end
if redis.call('HGET', KEYS[1], 'execution_id') ~= ARGV[7]
  or redis.call('HGET', KEYS[1], 'lease_owner_id') ~= ARGV[8]
  or redis.call('HGET', KEYS[1], 'lease_fencing_token') ~= ARGV[9]
  or tonumber(redis.call(
    'HGET', KEYS[1], 'lease_expires_at_ms') or '0') <= current_time then
  return {-6, 'lost'}
end
local payload = redis.call('HGET', KEYS[1], 'payload')
if not payload then return {-2, 'corrupted'} end
local retention_until = current_time + tonumber(ARGV[4])
redis.call('HSET', KEYS[1], 'state', 'consumed',
  'consumed_at_ms', tostring(current_time),
  'retention_until_ms', tostring(retention_until),
  'consume_operation_id', ARGV[6])
redis.call('HDEL', KEYS[1], 'payload', 'payload_digest', 'lease_owner_id',
  'lease_acquired_at_ms', 'lease_expires_at_ms')
redis.call('PEXPIREAT', KEYS[1], retention_until)
return {1, payload}
"""
