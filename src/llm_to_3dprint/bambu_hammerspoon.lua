local application = require("hs.application")
local eventtap = require("hs.eventtap")
local timer = require("hs.timer")

local M = {}
local BAMBU_BUNDLE_ID = "com.bambulab.bambu-studio"
local BAMBU_APP_NAMES = { "Bambu Studio", "BambuStudio" }
local MERGE_DIALOG_TITLE = "Object with multiple parts was detected"
local MERGE_DIALOG_CLICK_X_FRACTION = 0.75
local MERGE_DIALOG_CLICK_Y_FRACTION = 0.78

local function normalize_point(x, y)
  return { x = tonumber(x), y = tonumber(y) }
end

function M.ping()
  return {
    ok = true,
    action = "ping",
  }
end

function M.activate_app(app_name)
  local app = nil
  local target = app_name

  if app_name == "BambuStudio" or app_name == "Bambu Studio" then
    application.launchOrFocusByBundleID(BAMBU_BUNDLE_ID)
    timer.usleep(1000000)
    app = application.applicationsForBundleID(BAMBU_BUNDLE_ID)[1]
    if app == nil then
      for _, candidate in ipairs(BAMBU_APP_NAMES) do
        application.launchOrFocus(candidate)
        timer.usleep(500000)
        app = application.get(candidate)
        if app ~= nil then
          target = candidate
          break
        end
      end
    else
      target = "Bambu Studio"
    end
  else
    app = application.get(app_name)
  end

  if app == nil then
    application.launchOrFocus(target)
    timer.usleep(500000)
    app = application.get(target)
  else
    app:activate(true)
    timer.usleep(250000)
  end

  return {
    ok = app ~= nil,
    action = "activate_app",
    app_name = target,
  }
end

function M.click_point(x, y)
  local point = normalize_point(x, y)
  eventtap.leftClick(point)
  return {
    ok = true,
    action = "click_point",
    x = point.x,
    y = point.y,
  }
end

function M.bambu_click_merge_confirm(x, y)
  local activation = M.activate_app("BambuStudio")
  if not activation.ok then
    return {
      ok = false,
      action = "bambu_click_merge_confirm",
      reason = "failed_to_activate_bambu",
    }
  end

  local wf = require("hs.window.filter")
  local windows = wf.new(false):setAppFilter("Bambu Studio"):getWindows()
  local targetPoint = nil
  local strategy = "absolute_fallback"
  for _, win in ipairs(windows) do
    if win:title() == MERGE_DIALOG_TITLE then
      local frame = win:frame()
      targetPoint = {
        x = math.floor(frame.x + frame.w * MERGE_DIALOG_CLICK_X_FRACTION + 0.5),
        y = math.floor(frame.y + frame.h * MERGE_DIALOG_CLICK_Y_FRACTION + 0.5),
      }
      strategy = "dialog_relative"
      break
    end
  end

  if targetPoint == nil then
    targetPoint = normalize_point(x, y)
  end

  timer.usleep(250000)
  local clicked = M.click_point(targetPoint.x, targetPoint.y)
  clicked.action = "bambu_click_merge_confirm"
  clicked.strategy = strategy
  return clicked
end

return M
