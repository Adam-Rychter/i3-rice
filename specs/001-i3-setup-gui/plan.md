# Implementation Plan: i3 Setup and Customization GUI Prototype

**Branch**: Not yet created | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)

**Input**: Umbrella feature specification in `spec.md` and prototype decisions
made with the user.

**Status**: In progress. The application shell, discovery, and an in-memory
i3 inner-gap draft are implemented; VM preparation and VM validation remain
outstanding.

## Summary

Build a Python/PySide6 desktop prototype that demonstrates the full existing
component stack with a small, explicitly defined set of controls per component,
an adjacent editable configuration view, and apt package installation. Test
actual installation and desktop changes only in an isolated Ubuntu 24.04 VM
running on VMware.
Use fixture files for automated tests and early development.

The prototype is a learning milestone, not the first release defined by the
umbrella specification. Features outside the prototype remain requirements for
that release; they are not silently dropped or considered complete.

## Technical Context

**Language/Version**: Python; exact minimum version to be confirmed against the
chosen VM distribution. Python 3.11+ is a planning baseline, not a confirmed
support commitment.

**Primary Dependencies**: PySide6 (Qt for Python); i3 and the existing desktop
components under test; apt on the prototype VM. Version pinning and packaging
will be selected after verifying availability on the chosen distribution.

**Storage**: Existing user configuration files; user-owned backups and
transaction metadata; test fixtures in temporary directories. Exact backup and
state paths will be specified before implementation.

**Testing**: `pytest` for parsing, synchronization, safety, and backend tests;
Qt-aware tests for GUI interactions; isolated X11/i3 VM tests for real
installation, reload, preview, and recovery. No tests may install packages or
write real user configuration outside the disposable VM.

**Target Platform**: Ubuntu 24.04 in an isolated VMware VM, with an existing
graphical session. Live i3 preview requires an i3/X11 session; inspection and
setup must also work from the VM's existing non-i3 graphical session.

**Project Type**: Local Linux desktop application, with a narrowly scoped
privileged installation mechanism and an independent preview-recovery process.

**Performance Goals**: No agreed numerical targets yet. Detection, installation,
validation, and builds must not block the GUI; operations must expose progress
or an indeterminate state.

**Constraints**: Preserve existing configuration; do not change administrator
groups; obtain explicit approval before installation; never run the whole GUI
as root; avoid executing configuration content as shell code. Live previews
must time out after 30 seconds and survive GUI failure.

**Scale/Scope**: One user, one local machine, a curated set of existing
components, and a small set of demonstrated settings. Prototype support is
restricted to apt and the selected Ubuntu 24.04 VM.

### GUI Toolkit Decision

- **Selected**: PySide6, because Qt Widgets and Python bindings provide desktop
  controls, an editor, and flexible styling without requiring a browser.
- **Alternative considered**: GTK 4/PyGObject with libadwaita offers strong Linux
  integration, but introduces distribution-provided GTK/GObject dependencies and
  a different virtual-environment setup. Either is viable; PySide6 was chosen
  for this prototype after the comparison was presented.
- **Deployment caveat**: Verify Qt/PySide licensing obligations and packaging
  compatibility before distributing builds; do not treat toolkit selection as a
  license decision for this repository.
- **References**: [Qt for Python](https://doc.qt.io/qtforpython-6.11/),
  [PyGObject installation](https://pygobject.gnome.org/getting_started.html).

## Constitution Check

No Spec Kit constitution was found in the repository. No project-specific
constitution gates can be asserted. Until one exists, apply these plan-level
safety gates before implementation and re-check them at each milestone:

1. The GUI runs unprivileged; elevation is limited to approved package actions.
2. No admin-group changes, silent config replacement, or unapproved installation.
3. Development starts with fixtures; actual changes are tested only in an
   isolated VM with a snapshot and an accessible recovery path.
4. Unsupported or ambiguous configuration is preserved and its unsafe controls
   disabled; errors and partial failures are visible.
5. A live-preview path is not enabled until its independent timed recovery and
   conflict handling have passed tests.

## Prototype Scope

### In scope

1. **Application shell**: Component navigation, status, errors, a settings area,
   an adjacent configuration snippet editor, a full-file editor, and
   progress/confirmation dialogs. Use a coherent visual theme; exact styling
   is an implementation decision.
2. **Discovery**: Detect the graphical session, i3 availability, supported
   component executables and relevant configuration paths. Distinguish
   installed, missing, and unknown states without claiming package ownership
   based solely on an executable's presence.
3. **Apt setup**: Select from a small curated package catalog for the existing
   stack; show installed/missing/unknown status, a proposed install plan, and
   actions requiring elevation. After approval, install selected supported apt
   packages and report each operation's result. Unknown mappings or unavailable
   packages are reported, not silently skipped.
4. **Component examples**: Implement and demonstrate a few recognized controls
   for each area below. Exact supported syntax and ranges are defined using
   fixtures before implementation; controls remain disabled when the target
   cannot be safely understood or applied.

   | Area | Initial candidate controls or workflows |
   |---|---|
   | i3 | Gaps and borders |
   | Workspaces and keybindings | Workspace labels and selected bindings, with conflict warnings |
   | Polybar | Bar height and selected module/layout values |
   | Rofi | Background color and border radius |
   | Picom | Corner radius and shadow settings |
   | Dunst | Frame color and notification width |
   | Wallpaper | Choose an existing image and configure the supported startup reference |
   | st | Inspect source/config availability; edit selected font/color settings only when a safe rebuild and apply path is available |
   | Fonts and scaling | Selected supported font and scaling values, with affected components identified |
   | Displays | Inspect connected displays and offer a small set of supported arrangement settings only with a tested recovery path |

5. **Bidirectional editing**: For recognized settings, synchronize GUI controls
   and manual snippet/full-file edits. Preserve unrelated text and comments.
   Recognize supported included files and shared variables where safely
   resolvable; otherwise clearly disable unsafe controls. Show affected uses
   before changing a shared variable and offer the choice described in FR-031.
6. **Validation, backups, and conflicts**: Validate staged changes when a
   reliable validator exists; block known-invalid changes. If validation is
   unavailable, explain this and request explicit confirmation. Back up
   application-managed configuration and offer restoration. Detect external
   edits; prompt before discarding drafts and block conflicting application
   until resolved.
7. **Preview**: Implement live preview for a limited, explicitly verified
   subset in an i3 VM session. Confirm, cancel, or automatically revert after
   30 seconds using recovery independent of the GUI. Settings without safe
   preview use a clearly explained, explicitly confirmed apply workflow.
8. **Shared palette**: Demonstrate one shared color propagated to at least two
   supported components, with all affected edits visible before application.

### Deferred beyond the prototype

- Package managers other than apt, the full release distribution matrix, and
  repository-or-source installation choices.
- Downloading and building curated upstream projects, including initial st
  installation. If an existing st source tree cannot be rebuilt safely, its
  build-dependent controls are disabled rather than simulated.
- Full breadth of controls, full syntax coverage, and component alternatives.
- Saved profiles and import/export, beyond configuration backups.
- A complete palette/preset system and release packaging/distribution.
- Replacing or removing `install-i3-rice.sh`. The GUI ultimately replaces the
  standalone installer as specified, but the prototype must not remove it.

## Design and Safety Decisions

### Configuration editing

- Separate UI state, document parsing, component adapters, validation, and disk
  operations. Parse only explicitly supported syntax; preserve original bytes
  outside narrowly identified edits. Treat ambiguous duplicates, unsupported
  includes, and unresolved variables as unsafe rather than guessing.
- Maintain a baseline fingerprint for every opened file. Recheck immediately
  before preview, apply, and restore. On a conflict, retain the draft and block
  writes until the user resolves it; provide explicit reload/discard and review
  paths. Never silently overwrite external edits.
- Stage a complete proposed change before writing. Show affected files and
  changes; validate the staged representation using each component's available
  validator. Verify that staged included-file validation actually checks the
  staged files rather than the live originals; if not, report validation as
  unavailable instead of claiming success.
- Back up original files before modification and write atomically where
  supported. A multi-file operation must track which writes succeeded and
  report partial failures; do not promise atomicity across files.

### Live preview and recovery

- Define an explicit preview transaction containing the original content,
  expected preview fingerprints, affected files, reload operations, state, and
  deadline. Start an independent unprivileged watchdog before applying a
  preview. Serialize confirmation and rollback so a timeout cannot race a
  confirmation.
- On timeout or cancellation, restore only files still matching the expected
  preview state, then attempt the appropriate component reload. If a file
  changed externally, do not overwrite it; report a recovery conflict and
  preserve both the backup and external content for user resolution. Automatic
  full restoration in this conflict cannot be guaranteed and must not be
  reported as successful.
- Test GUI termination and unresponsiveness. A watchdog failure, failed reload,
  or uncertain recovery blocks or ends preview with a visible error. Behavior
  across full graphical-session or machine failure remains an open release
  design question.
- Non-previewable settings require an explicit confirmation; display changes
  remain disabled until a separately verified recovery procedure exists.

### Installation

- Do not invoke the existing installer as a backend: it writes full configs,
  may change admin-group membership, and continues after some install failures.
  Reuse its package mappings only after checking them against the VM's actual
  package sources and prototype catalog.
- Run the GUI as the logged-in user. Design and test a narrowly scoped
  privilege boundary for approved apt operations; the authorization mechanism
  is an implementation research decision. Do not pass passwords through the
  GUI or execute user-provided shell commands.
- Resolve package names from the curated catalog, use argument arrays rather
  than shell interpolation, and display planned package operations and their
  outcome. Handle authorization refusal, locked package manager, unavailable
  package, cancellation, and partial install honestly. Do not alter groups.

## Project Structure

### Documentation

```text
specs/001-i3-setup-gui/
├── spec.md              # Umbrella product specification
├── plan.md              # This prototype plan
├── research.md          # Future focused research, if needed
├── data-model.md        # Future design, if needed
├── contracts/           # Future contracts, if needed
└── tasks.md             # Future implementation task breakdown
```

### Proposed Source Code

```text
src/i3_rice_gui/
├── app.py               # Application entry point
├── ui/                  # PySide6 screens, controls, and editors
├── components/          # Component-specific discovery and setting adapters
├── config/              # Documents, narrow edits, validation, backups
├── install/             # Catalog, apt planning, and execution boundary
└── preview/             # Preview transactions and recovery process
tests/
├── fixtures/            # Representative configs and edge cases
├── unit/                # Parsing, planning, and transaction logic
├── integration/         # Temporary-filesystem and GUI integration tests
└── vm/                  # Isolated VM acceptance procedures and tests
```

**Structure Decision**: One local Python application with separated domain and
UI modules. The tree is proposed, not existing code. Keep `install-i3-rice.sh`
and existing project files unchanged during early prototype work.

## Implementation Milestones

1. **VM and design baseline**: Prepare Ubuntu 24.04 in VMware and create a
   disposable VM snapshot; inventory component versions, config
   locations, validators, apt packages, authorization, and i3/X11 test access.
   Define representative fixtures and the precise controls feasible for each
   component.
2. **Application shell and discovery**: Establish Python/PySide6 project setup,
   component navigation, status and error handling. Verify startup in both
   non-i3 and i3 graphical sessions without modifying the desktop.
   The read-only shell and discovery implementation are complete and tested
   locally offscreen; startup verification in both VM sessions remains open.
3. **Editing foundation**: Implement document baselines, narrow preservation
   edits, snippet/full-file synchronization, validation, backup, restore, and
   external-change blocking. Cover basic values first; add supported includes
   and shared-variable handling with targeted tests.
   Started with in-memory drafts, checked range edits, diffs, external-change
   detection, and a draft-only i3 inner-gap slider and code field. Configuration
   writing, validation, backups, and full-file editing are not enabled yet.
4. **Component slices**: Add the prototype controls for each listed area,
   including safe disabled states for missing, ambiguous, or unsupported
   configurations. Verify both editing directions and preservation for every
   enabled control. Document controls that remain disabled and why.
5. **Apt setup**: Add curated package detection, plan review, bounded
   authorization and execution, and honest per-operation results. Exercise
   success and failure cases in the VM; never call the old installer.
6. **Preview and recovery**: Implement independent timed rollback and
   confirmation/cancellation for a small verified subset, then add additional
   previewable controls only after their recovery tests pass. Test GUI crash
   and conflict behavior in the VM.
7. **Integrated demonstration**: In a restored VM snapshot, install a selected
   missing package, inspect every component, edit and validate supported
   settings, preview and revert a change, confirm another, restore a backup,
   and demonstrate an external edit conflict. Record limitations and decide
   which feature-level specifications and tasks come next.

Milestones can overlap only after their prerequisites are available; no
live-preview UI is enabled before milestone 6 safety gates pass. This is a
plan, not a commitment to bypass the umbrella release requirements.

## Prototype Acceptance and Verification

- Fixture tests show both editing directions, preservation of unknown content,
  and safe handling of supported includes, variables, duplicates, and invalid
  input. Unsupported patterns must produce an explicit disabled state.
- A reviewable apt plan is required before any package operation; authorization
  refusal, package failure, and partial results are visible. No administrator
  group membership is modified.
- A VM test confirms backup and restore, external-change blocking, and no
  unintended overwrite. Test directories and snapshots are isolated from the
  host's real home and package database.
- A verified live preview reverts on timeout, cancellation, GUI termination,
  and GUI unresponsiveness; confirmation keeps it. Recovery conflicts are
  reported without overwriting externally modified files.
- Every component area is visible in the GUI, and every enabled control works
  against a documented supported fixture or VM configuration. Unsupported
  controls and operations are visibly unavailable, never decorative successes.
- At least one shared color updates two supported components through a reviewed
  change; failures or conflicts in either are surfaced.
- The prototype works from the VM's existing graphical session for setup and
  inspection; live i3 preview is available only in the verified i3/X11 session.

## Open Decisions Before Implementation

1. Which existing graphical session will be used on the Ubuntu VM, and how
   will an i3/X11 session be made available for preview testing?
2. What precise control ranges and supported config syntax will each component
   prototype demonstrate? In particular, what existing st source/build state
   is available?
3. Which privilege mechanism is available on the selected VM, and how will its
   permitted apt actions be constrained and tested?
4. What paths and retention policy should backups and preview transaction data
   use? How should the user resolve a recovery conflict?
5. How should the independent watchdog coordinate durable confirmation and
   timeout races, and which desktop changes have a reliable recovery path?
6. Which validators and reload mechanisms are present for the selected
   component versions, including staged included files?

## Complexity Tracking

No constitution exists, so there are no recorded constitution violations.
Independent preview recovery and a limited privilege boundary are necessary for
the safety requirements; their exact implementation remains to be researched.
