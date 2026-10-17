"""Format the server identity using documented TVHeadend HTTP API fields.

TVHeadend /api/serverinfo reports its software as "name", not "server_name".
The user's connection name is supplied separately by the local configuration.
"""


def format_server_information(configured, api_data=None):
    configured = configured if isinstance(configured, dict) else {}
    connection_name = configured.get("name") or "Unnamed connection"
    address = configured.get("url") or "Not configured"

    lines = [
        "Server Information:",
        "",
        f"Server Name: {connection_name}",
        f"URL: {address}",
    ]
    if isinstance(api_data, dict):
        lines.extend((
            "",
            f"Server Version: {api_data.get('sw_version') or 'Not reported'}",
            f"API Version: {api_data.get('api_version') or 'Not reported'}",
            f"Software: {api_data.get('name') or 'Not reported'}",
        ))
        capabilities = api_data.get("capabilities")
        if isinstance(capabilities, list):
            lines.extend(("", "Capabilities:"))
            lines.extend(f"- {cap}" for cap in capabilities if isinstance(cap, str))
    return "\n".join(lines)
