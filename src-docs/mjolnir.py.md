<!-- markdownlint-disable -->

<a href="../src/draupnir.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `draupnir.py`
Provide the Draupnir class to represent the Draupnir plugin for Synapse. 

**Global Variables**
---------------
- **DRAUPNIR_SERVICE_NAME**
- **USERNAME**


---

## <kbd>class</kbd> `Draupnir`
A class representing the Draupnir plugin for Synapse application. 

Draupnir is a moderation tool for Matrix to be used to protect your server from malicious invites, spam messages etc. See https://github.com/the-draupnir-project/draupnir/ for more details about it. 

<a href="../src/draupnir.py#L33"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBaseWithState, token_service: AdminAccessTokenService)
```

Initialize a new instance of the Draupnir class. 



**Args:**
 
 - <b>`charm`</b>:  The charm object that the Draupnir instance belongs to. 
 - <b>`token_service`</b>:  Instance of Admin Access Token Service. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 



---

<a href="../src/draupnir.py#L171"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `enable_draupnir`

```python
enable_draupnir(charm_state: CharmState, admin_access_token: str) → None
```

Enable draupnir service. 

The required steps to enable Draupnir are: 
 - Get an admin access token. 
 - Check if the DRAUPNIR_MEMBERSHIP_ROOM room is created. 
 -- Only users from there will be allowed to join the management room. 
 - Create Draupnir user or get its access token if already exists. 
 - Create the management room or get its room id if already exists. 
 -- The management room will allow only members of DRAUPNIR_MEMBERSHIP_ROOM room to join it. 
 - Make the Draupnir user admin of this room. 
 - Create the Draupnir configuration file. 
 - Override Draupnir user rate limit. 
 - Finally, add Draupnir pebble layer. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState. 
 - <b>`admin_access_token`</b>:  not empty admin access token. 

---

<a href="../src/draupnir.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_charm`

```python
get_charm() → CharmBaseWithState
```

Return the current charm. 



**Returns:**
  The current charm 

---

<a href="../src/draupnir.py#L158"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_membership_room_id`

```python
get_membership_room_id(admin_access_token: str) → Optional[str]
```

Check if membership room exists. 



**Args:**
 
 - <b>`admin_access_token`</b>:  not empty admin access token. 



**Returns:**
 The room id or None if is not found. 


