--[[
    BG3 Character Export Script for bg3-to-5e converter

    Usage:
    1. Open BG3 Script Extender console (~)
    2. Run: Ext.Require("bg3_export.lua")
    3. Run: export5e()

    The export will be saved to:
    ~/.local/share/Larian Studios/Baldur's Gate 3/Script Extender/party_export.json
    or
    %LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Script Extender\party_export.json
]]

local function getAbilityScores(entity)
    local abilities = {}
    local abilityNames = {"Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"}

    for _, ability in ipairs(abilityNames) do
        local stat = entity:GetComponent("stats")[ability]
        if stat then
            abilities[ability] = stat.Value or stat.BaseValue or 10
        else
            abilities[ability] = 10
        end
    end

    return abilities
end

local function getClasses(entity)
    local classes = {}
    local classManager = entity:GetComponent("ClassesContainer")

    if classManager and classManager.Classes then
        for _, classData in pairs(classManager.Classes) do
            local classInfo = {
                name = classData.ClassUUID,
                level = classData.Level or 1,
                subclass = classData.SubClassUUID,
                internalName = classData.ClassUUID,
                internalSubclass = classData.SubClassUUID
            }

            -- Try to get readable names
            local classResource = Ext.StaticData.Get(classData.ClassUUID, "ClassDescription")
            if classResource then
                classInfo.name = classResource.Name or classInfo.name
            end

            if classData.SubClassUUID then
                local subclassResource = Ext.StaticData.Get(classData.SubClassUUID, "ClassDescription")
                if subclassResource then
                    classInfo.subclass = subclassResource.Name or classInfo.subclass
                end
            end

            table.insert(classes, classInfo)
        end
    end

    return classes
end

local function getSpells(entity)
    local spells = {}
    local spellBook = entity:GetComponent("SpellBook")

    if spellBook and spellBook.Spells then
        for _, spellEntry in pairs(spellBook.Spells) do
            local spell = {
                name = spellEntry.SpellId,
                level = 0,
                prepared = spellEntry.Prepared or false,
                internalName = spellEntry.SpellId
            }

            -- Try to get spell data
            local spellData = Ext.Stats.Get(spellEntry.SpellId)
            if spellData then
                spell.level = spellData.Level or 0
                spell.school = spellData.SpellSchool
            end

            -- Get readable name
            local spellResource = Ext.StaticData.Get(spellEntry.SpellId, "SpellData")
            if spellResource and spellResource.DisplayName then
                spell.name = Ext.Loca.GetTranslatedString(spellResource.DisplayName) or spell.name
            end

            table.insert(spells, spell)
        end
    end

    return spells
end

local function getEquipment(entity)
    local equipment = {}
    local inventory = entity:GetComponent("InventoryOwner")

    if inventory then
        local items = inventory:GetAllItems()
        if items then
            for _, itemHandle in ipairs(items) do
                local item = Ext.Entity.Get(itemHandle)
                if item then
                    local itemData = {
                        name = "Unknown Item",
                        type = "misc",
                        equipped = false,
                        quantity = 1,
                        magical = false
                    }

                    local itemComponent = item:GetComponent("Item")
                    if itemComponent then
                        itemData.name = itemComponent.StatsId or "Unknown"
                        itemData.quantity = itemComponent.Amount or 1
                    end

                    local equipSlot = item:GetComponent("Equipable")
                    if equipSlot then
                        itemData.equipped = equipSlot.Slot ~= nil
                        itemData.type = equipSlot.Slot or "misc"
                    end

                    -- Check if magical
                    local itemStats = Ext.Stats.Get(itemData.name)
                    if itemStats then
                        itemData.magical = itemStats.Rarity ~= "Common"
                    end

                    table.insert(equipment, itemData)
                end
            end
        end
    end

    return equipment
end

local function getFeatures(entity)
    local features = {}
    local passives = entity:GetComponent("PassiveContainer")

    if passives and passives.Passives then
        for _, passive in pairs(passives.Passives) do
            local feature = {
                name = passive.PassiveId,
                source = passive.Source or "unknown",
                internalName = passive.PassiveId
            }

            -- Get readable name
            local passiveResource = Ext.StaticData.Get(passive.PassiveId, "PassiveData")
            if passiveResource and passiveResource.DisplayName then
                feature.name = Ext.Loca.GetTranslatedString(passiveResource.DisplayName) or feature.name
            end

            table.insert(features, feature)
        end
    end

    return features
end

local function getIllithidPowers(entity)
    local powers = {}
    local tadpole = entity:GetComponent("TadpoleTreeState")

    if tadpole and tadpole.UnlockedPowers then
        for _, powerId in pairs(tadpole.UnlockedPowers) do
            local power = {
                name = powerId,
                source = "illithid",
                internalName = powerId
            }

            -- Get readable name
            local powerResource = Ext.StaticData.Get(powerId, "PassiveData")
            if powerResource and powerResource.DisplayName then
                power.name = Ext.Loca.GetTranslatedString(powerResource.DisplayName) or power.name
            end

            table.insert(powers, power)
        end
    end

    return powers
end

local function getSkills(entity)
    local skills = {}
    local expertise = entity:GetComponent("Expertise")
    local proficiencies = entity:GetComponent("Proficiency")

    local skillList = {
        "Acrobatics", "AnimalHandling", "Arcana", "Athletics",
        "Deception", "History", "Insight", "Intimidation",
        "Investigation", "Medicine", "Nature", "Perception",
        "Performance", "Persuasion", "Religion", "SleightOfHand",
        "Stealth", "Survival"
    }

    for _, skill in ipairs(skillList) do
        local proficient = false
        local hasExpertise = false

        if proficiencies and proficiencies.Proficiencies then
            for _, prof in pairs(proficiencies.Proficiencies) do
                if prof.Type == skill then
                    proficient = true
                    break
                end
            end
        end

        if expertise and expertise.Expertise then
            for _, exp in pairs(expertise.Expertise) do
                if exp == skill then
                    hasExpertise = true
                    break
                end
            end
        end

        skills[skill] = {
            proficient = proficient,
            expertise = hasExpertise
        }
    end

    return skills
end

local function getSavingThrows(entity)
    local saves = {}
    local proficiencies = entity:GetComponent("Proficiency")
    local abilities = {"Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"}

    for _, ability in ipairs(abilities) do
        saves[ability] = false

        if proficiencies and proficiencies.Proficiencies then
            for _, prof in pairs(proficiencies.Proficiencies) do
                if prof.Type == ability .. "Saving" then
                    saves[ability] = true
                    break
                end
            end
        end
    end

    return saves
end

local function exportCharacter(entity)
    local name = "Unknown"
    local race = "Unknown"
    local subrace = nil
    local background = nil

    -- Get display name
    local displayName = entity:GetComponent("DisplayName")
    if displayName then
        name = displayName.Name or displayName.NameKey or "Unknown"
        if displayName.NameKey then
            local translated = Ext.Loca.GetTranslatedString(displayName.NameKey)
            if translated then
                name = translated
            end
        end
    end

    -- Get race
    local raceComponent = entity:GetComponent("Race")
    if raceComponent then
        race = raceComponent.Race or "Unknown"
        local raceResource = Ext.StaticData.Get(raceComponent.Race, "Race")
        if raceResource then
            race = raceResource.Name or race
            if raceResource.ParentGuid then
                subrace = race
                local parentRace = Ext.StaticData.Get(raceResource.ParentGuid, "Race")
                if parentRace then
                    race = parentRace.Name or race
                end
            end
        end
    end

    -- Get background
    local backgroundComponent = entity:GetComponent("Background")
    if backgroundComponent then
        background = backgroundComponent.Background or nil
        local bgResource = Ext.StaticData.Get(backgroundComponent.Background, "Background")
        if bgResource then
            background = bgResource.DisplayName or background
        end
    end

    -- Get health
    local health = entity:GetComponent("Health")
    local maxHp = 10
    local currentHp = 10
    if health then
        maxHp = health.MaxHp or health.Hp or 10
        currentHp = health.Hp or maxHp
    end

    -- Get armor class
    local ac = 10
    local armor = entity:GetComponent("Armor")
    if armor then
        ac = armor.ArmorClass or 10
    end

    -- Get movement speed
    local speed = 30
    local movement = entity:GetComponent("Movement")
    if movement then
        speed = movement.Speed or 30
    end

    -- Get gold (simplified)
    local gold = 0
    local inventory = entity:GetComponent("InventoryOwner")
    if inventory then
        -- Would need to search inventory for gold items
        gold = 0
    end

    return {
        name = name,
        uuid = tostring(entity.Uuid),
        race = race,
        subrace = subrace,
        background = background,
        classes = getClasses(entity),
        abilities = getAbilityScores(entity),
        maxHp = maxHp,
        currentHp = currentHp,
        tempHp = 0,
        armorClass = ac,
        speed = speed,
        proficiencyBonus = 2, -- Would need to calculate based on level
        savingThrows = getSavingThrows(entity),
        skills = getSkills(entity),
        spells = getSpells(entity),
        spellSlots = {}, -- Would need to calculate based on class
        equipment = getEquipment(entity),
        gold = gold,
        features = getFeatures(entity),
        tadpolePowers = getIllithidPowers(entity),
        inspiration = 0
    }
end

function export5e()
    local party = {}
    local partyComponent = Ext.Entity.Get(Osi.GetHostCharacter()):GetComponent("PartyMember")

    if partyComponent and partyComponent.Party then
        local partyEntity = Ext.Entity.Get(partyComponent.Party)
        if partyEntity then
            local partyMembers = partyEntity:GetComponent("PartyComposition")
            if partyMembers and partyMembers.Members then
                for _, memberHandle in pairs(partyMembers.Members) do
                    local member = Ext.Entity.Get(memberHandle)
                    if member then
                        local charData = exportCharacter(member)
                        table.insert(party, charData)
                        print("[bg3-to-5e] Exported: " .. charData.name)
                    end
                end
            end
        end
    end

    -- Fallback: export just the host character
    if #party == 0 then
        local host = Ext.Entity.Get(Osi.GetHostCharacter())
        if host then
            local charData = exportCharacter(host)
            table.insert(party, charData)
            print("[bg3-to-5e] Exported: " .. charData.name)
        end
    end

    local exportData = {
        exportVersion = "1.0",
        exportDate = os.date("%Y-%m-%d %H:%M:%S"),
        party = party
    }

    -- Save to file
    local json = Ext.Json.Stringify(exportData, true)
    local success = Ext.IO.SaveFile("party_export.json", json)

    if success then
        print("[bg3-to-5e] Export complete! Saved to Script Extender/party_export.json")
        print("[bg3-to-5e] Exported " .. #party .. " character(s)")
    else
        print("[bg3-to-5e] ERROR: Failed to save export file")
    end

    return exportData
end

-- Print load message
print("[bg3-to-5e] Character export script loaded!")
print("[bg3-to-5e] Run export5e() to export your party")
