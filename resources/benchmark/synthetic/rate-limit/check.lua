local count = {}
response = function(status, headers, body)
  count[status] = (count[status] or 0) + 1
end

done = function(summary, latency, requests)
  for k,v in pairs(count) do
    io.write(string.format("HTTP %s: %d\n", k, v))
  end
end
