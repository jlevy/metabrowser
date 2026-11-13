import AppKit

/// The menu bar, built in code. Items with a nil target travel the responder chain:
/// the key window's web view answers Cut, Copy, Paste, Select All, and Undo itself,
/// its window controller answers the page and server items, and the app delegate
/// answers the rest. Without an Edit menu, Command-C and Command-V do nothing in a web
/// view. The page binds plain keys and Command-1 to Command-3; the shortcuts here
/// stay clear of those.
enum MainMenu {
    static func build(recentFolders: NSMenuDelegate) -> NSMenu {
        let main = NSMenu()
        main.addSubmenu("Metabrowser", [
            item("About Metabrowser", #selector(NSApplication.orderFrontStandardAboutPanel(_:))),
            .separator(),
            item("Settings…", #selector(AppDelegate.showSettings(_:)), ","),
            .separator(),
            item("Hide Metabrowser", #selector(NSApplication.hide(_:)), "h"),
            item("Hide Others", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
            item("Show All", #selector(NSApplication.unhideAllApplications(_:))),
            .separator(),
            item("Quit Metabrowser", #selector(NSApplication.terminate(_:)), "q"),
        ])

        let recent = NSMenu(title: "Open Recent")
        recent.delegate = recentFolders
        let recentHolder = NSMenuItem(title: "Open Recent", action: nil, keyEquivalent: "")
        recentHolder.submenu = recent
        main.addSubmenu("File", [
            item("Open…", #selector(AppDelegate.openFolder(_:)), "o"),
            recentHolder,
            .separator(),
            item("Close Window", #selector(NSWindow.performClose(_:)), "w"),
            .separator(),
            item("Restart Server", #selector(BrowserWindowController.restartServer(_:)), "r", [.command, .option]),
            item("Open in Default Browser", #selector(BrowserWindowController.openInDefaultBrowser(_:))),
            item("Reveal Server Log", #selector(BrowserWindowController.revealServerLog(_:))),
            .separator(),
            item("Print…", #selector(BrowserWindowController.printPage(_:)), "p"),
        ])

        let find = NSMenu(title: "Find")
        for (title, action, key, modifiers) in [
            ("Find…", NSTextFinder.Action.showFindInterface, "f", NSEvent.ModifierFlags.command),
            ("Find Next", .nextMatch, "g", .command),
            ("Find Previous", .previousMatch, "g", [.command, .shift]),
            ("Use Selection for Find", .setSearchString, "e", .command),
        ] {
            let findItem = item(title, #selector(BrowserWindowController.performFindAction(_:)), key, modifiers)
            findItem.tag = action.rawValue
            find.addItem(findItem)
        }
        let findHolder = NSMenuItem(title: "Find", action: nil, keyEquivalent: "")
        findHolder.submenu = find
        main.addSubmenu("Edit", [
            item("Undo", Selector(("undo:")), "z"),
            item("Redo", Selector(("redo:")), "z", [.command, .shift]),
            .separator(),
            item("Cut", #selector(NSText.cut(_:)), "x"),
            item("Copy", #selector(NSText.copy(_:)), "c"),
            item("Paste", #selector(NSText.paste(_:)), "v"),
            item("Select All", #selector(NSText.selectAll(_:)), "a"),
            .separator(),
            findHolder,
        ])

        main.addSubmenu("View", [
            item("Back", #selector(BrowserWindowController.navigateBack(_:)), "["),
            item("Forward", #selector(BrowserWindowController.navigateForward(_:)), "]"),
            item("Reload Page", #selector(BrowserWindowController.reloadPage(_:)), "r"),
            .separator(),
            item("Actual Size", #selector(BrowserWindowController.actualSize(_:)), "0"),
            item("Zoom In", #selector(BrowserWindowController.zoomIn(_:)), "="),
            item("Zoom Out", #selector(BrowserWindowController.zoomOut(_:)), "-"),
            .separator(),
            item("Enter Full Screen", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]),
        ])

        NSApp.windowsMenu = main.addSubmenu("Window", [
            item("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"),
            item("Zoom", #selector(NSWindow.performZoom(_:))),
            .separator(),
            item("Bring All to Front", #selector(NSApplication.arrangeInFront(_:))),
        ])
        NSApp.helpMenu = main.addSubmenu("Help", [
            item("Metabrowser Documentation", #selector(AppDelegate.openDocumentation(_:))),
            item("Reveal Logs Folder", #selector(AppDelegate.revealLogsFolder(_:))),
        ])
        return main
    }

    private static func item(
        _ title: String, _ action: Selector, _ key: String = "",
        _ modifiers: NSEvent.ModifierFlags = .command
    ) -> NSMenuItem {
        let menuItem = NSMenuItem(title: title, action: action, keyEquivalent: key)
        menuItem.keyEquivalentModifierMask = modifiers
        return menuItem
    }
}

extension NSMenu {
    @discardableResult
    fileprivate func addSubmenu(_ title: String, _ items: [NSMenuItem]) -> NSMenu {
        let submenu = NSMenu(title: title)
        items.forEach(submenu.addItem)
        let holder = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        holder.submenu = submenu
        addItem(holder)
        return submenu
    }
}
