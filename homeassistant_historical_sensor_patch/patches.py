# Code extracted and modified from
# homeassistant.helpers.entity.Entity._async_generate_attributes
# https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/entity.py
def _build_attributes(self: Entity) -> dict[str, Any]:
    """Calculate state string and attribute mapping."""
    entry = self.registry_entry

    attr = self.capability_attributes
    attr = dict(attr) if attr else {}

    available = self.available  # only call self.available once per update cycle
    if available:
        attr.update(self.state_attributes or {})
        attr.update(self.extra_state_attributes or {})

    if (unit_of_measurement := self.unit_of_measurement) is not None:
        attr[ATTR_UNIT_OF_MEASUREMENT] = unit_of_measurement

    if assumed_state := self.assumed_state:
        attr[ATTR_ASSUMED_STATE] = assumed_state

    if (attribution := self.attribution) is not None:
        attr[ATTR_ATTRIBUTION] = attribution

    if (
        device_class := (entry and entry.device_class) or self.device_class
    ) is not None:
        attr[ATTR_DEVICE_CLASS] = str(device_class)

    if (entity_picture := self.entity_picture) is not None:
        attr[ATTR_ENTITY_PICTURE] = entity_picture

    if (icon := (entry and entry.icon) or self.icon) is not None:
        attr[ATTR_ICON] = icon

    if (name := (entry and entry.name) or getattr(self, 'friendly_name', None)) is not None:
        attr[ATTR_FRIENDLY_NAME] = name

    if (supported_features := self.supported_features) is not None:
        attr[ATTR_SUPPORTED_FEATURES] = supported_features

    return attr
