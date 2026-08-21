import requests
import time
import traceback

token = "MTQ2MjgxMjE0OTAwODMwMjI2NQ.GJQwrq.xIXPeET4_cW_rdAmqyzZW4EPkpoF0YOjSFpeys"
source_guild_id = "1538386077964963981"
target_guild_id = "1540193874079916062"
headers = {"Authorization": token}

try:
    print("Starting advanced cloner (WITH CATEGORIES)...")
    
    test = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
    print(f"Logged in as: {test.json()['username']}")
    
    # ========== 1. CLONE ROLES SORTED ==========
    print("\n--- Cloning Roles ---")
    roles = requests.get(f"https://discord.com/api/v9/guilds/{source_guild_id}/roles", headers=headers).json()
    roles = [r for r in roles if r["name"] != "@everyone"]
    roles.sort(key=lambda x: x["position"], reverse=True)
    
    role_id_map = {}
    
    for role in roles:
        payload = {
            "name": role["name"],
            "permissions": str(role["permissions"]),
            "color": role["color"],
            "hoist": role["hoist"],
            "mentionable": role["mentionable"]
        }
        r = requests.post(f"https://discord.com/api/v9/guilds/{target_guild_id}/roles", headers=headers, json=payload)
        if r.status_code in [200, 201]:
            new_role_id = r.json()["id"]
            role_id_map[role["id"]] = new_role_id
            print(f"✓ {role['name']}")
        time.sleep(0.3)
    
    # ========== 2. REORDER ROLES ==========
    print("\n--- Reordering Roles ---")
    ordered_ids = [role_id_map[r["id"]] for r in roles if r["id"] in role_id_map]
    target_roles = requests.get(f"https://discord.com/api/v9/guilds/{target_guild_id}/roles", headers=headers).json()
    for tr in target_roles:
        if tr["name"] == "@everyone":
            ordered_ids.append(tr["id"])
            break
    
    r = requests.patch(f"https://discord.com/api/v9/guilds/{target_guild_id}/roles", headers=headers, json={"role_ids": ordered_ids})
    if r.status_code == 200:
        print(f"✓ Reordered {len(ordered_ids)-1} roles")
    
    # ========== 3. GET ALL CHANNELS FROM SOURCE ==========
    print("\n--- Fetching channels ---")
    channels = requests.get(f"https://discord.com/api/v9/guilds/{source_guild_id}/channels", headers=headers).json()
    
    # Separate categories and normal channels
    categories = [ch for ch in channels if ch["type"] == 4]  # type 4 = category
    normal_channels = [ch for ch in channels if ch["type"] != 4]
    
    # Sort categories by position
    categories.sort(key=lambda x: x["position"])
    
    category_id_map = {}  # Maps source category ID -> new category ID
    
    # ========== 4. CLONE CATEGORIES FIRST ==========
    print("\n--- Cloning Categories ---")
    for cat in categories:
        payload = {
            "name": cat["name"],
            "type": 4,
            "position": cat.get("position", 0)
        }
        r = requests.post(f"https://discord.com/api/v9/guilds/{target_guild_id}/channels", headers=headers, json=payload)
        if r.status_code in [200, 201]:
            new_cat_id = r.json()["id"]
            category_id_map[cat["id"]] = new_cat_id
            print(f"✓ Category: {cat['name']}")
        else:
            print(f"✗ Failed category: {cat['name']}")
        time.sleep(0.5)
    
    # ========== 5. CLONE NORMAL CHANNELS INTO CATEGORIES ==========
    print("\n--- Cloning Channels into Categories ---")
    channel_id_map = {}
    
    # Sort channels by their parent category and position
    for cat in categories:
        # Get channels that belong to this category
        channels_in_cat = [ch for ch in normal_channels if ch.get("parent_id") == cat["id"]]
        channels_in_cat.sort(key=lambda x: x["position"])
        
        for ch in channels_in_cat:
            payload = {
                "name": ch["name"],
                "type": ch["type"],
                "topic": ch.get("topic", ""),
                "nsfw": ch.get("nsfw", False),
                "rate_limit_per_user": ch.get("rate_limit_per_user", 0),
                "position": ch.get("position", 0),
                "parent_id": category_id_map.get(cat["id"])  # Assign to cloned category
            }
            r = requests.post(f"https://discord.com/api/v9/guilds/{target_guild_id}/channels", headers=headers, json=payload)
            if r.status_code in [200, 201]:
                new_channel_id = r.json()["id"]
                channel_id_map[ch["id"]] = new_channel_id
                print(f"  ✓ {ch['name']} → in {cat['name']}")
            else:
                print(f"  ✗ Failed: {ch['name']}")
            time.sleep(0.5)
    
    # ========== 6. CLONE CHANNELS WITH NO CATEGORY ==========
    print("\n--- Cloning Uncategorized Channels ---")
    orphan_channels = [ch for ch in normal_channels if ch.get("parent_id") is None]
    orphan_channels.sort(key=lambda x: x["position"])
    
    for ch in orphan_channels:
        payload = {
            "name": ch["name"],
            "type": ch["type"],
            "topic": ch.get("topic", ""),
            "nsfw": ch.get("nsfw", False),
            "rate_limit_per_user": ch.get("rate_limit_per_user", 0),
            "position": ch.get("position", 0)
        }
        r = requests.post(f"https://discord.com/api/v9/guilds/{target_guild_id}/channels", headers=headers, json=payload)
        if r.status_code in [200, 201]:
            new_channel_id = r.json()["id"]
            channel_id_map[ch["id"]] = new_channel_id
            print(f"✓ {ch['name']} (uncategorized)")
        else:
            print(f"✗ Failed: {ch['name']}")
        time.sleep(0.5)
    
    # ========== 7. CLONE PERMISSIONS ==========
    print("\n--- Cloning Permissions ---")
    # First clone permissions for categories
    for cat in categories:
        if cat["id"] not in category_id_map:
            continue
        new_cat_id = category_id_map[cat["id"]]
        
        for ow in cat.get("permission_overwrites", []):
            new_id = None
            if ow["type"] == 0 and ow["id"] in role_id_map:
                new_id = role_id_map[ow["id"]]
            elif ow["type"] == 1:
                new_id = ow["id"]
            
            if new_id:
                url = f"https://discord.com/api/v9/channels/{new_cat_id}/permissions/{new_id}"
                payload = {"allow": str(ow["allow"]), "deny": str(ow["deny"]), "type": ow["type"]}
                requests.put(url, headers=headers, json=payload)
                time.sleep(0.2)
    
    # Clone permissions for channels
    for ch in normal_channels:
        if ch["id"] not in channel_id_map:
            continue
        new_channel_id = channel_id_map[ch["id"]]
        
        for ow in ch.get("permission_overwrites", []):
            new_id = None
            if ow["type"] == 0 and ow["id"] in role_id_map:
                new_id = role_id_map[ow["id"]]
            elif ow["type"] == 1:
                new_id = ow["id"]
            
            if new_id:
                url = f"https://discord.com/api/v9/channels/{new_channel_id}/permissions/{new_id}"
                payload = {"allow": str(ow["allow"]), "deny": str(ow["deny"]), "type": ow["type"]}
                requests.put(url, headers=headers, json=payload)
                time.sleep(0.2)
    
    print(f"\n=== DONE ===")
    print(f"Roles cloned: {len(role_id_map)}")
    print(f"Categories cloned: {len(category_id_map)}")
    print(f"Channels cloned: {len(channel_id_map)}")

except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()

input("\nPress Enter to exit...")
