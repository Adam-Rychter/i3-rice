# Feature Specification: i3 Setup and Customization GUI

**Feature Branch**: Not yet created

**Created**: 2026-11-20

**Status**: Draft — collaborative product specification

**Input**: Evolve the existing i3 rice into a graphical tool that installs and
configures an i3 tiling desktop, with visual controls and directly editable
configuration code.

## User Scenarios & Testing

### User Story 1 - Inspect and Safely Edit an Existing Setup (Priority: P1)

A technical Linux user opens the application in an existing graphical session,
inspects their i3 setup, and adjusts supported settings without losing unrelated
customizations.

**Why this priority**: Preserving existing configurations and enabling informed
editing are foundational to a general-purpose tool.

**Independent Test**: Open a supported existing i3 configuration containing
custom directives, change a supported setting, apply it, and verify that the
requested change is present and unrelated directives remain intact.

**Acceptance Scenarios**:

1. **Given** a supported existing configuration, **When** the user opens a
   setting, **Then** the application shows its current value and relevant
   original configuration code.
2. **Given** a supported setting, **When** the user changes its GUI control or
   edits its code, **Then** the other representation reflects the change.
3. **Given** configuration the application cannot safely interpret, **When**
   it is encountered, **Then** it is preserved, the user is warned, and only
   controls that cannot safely operate are disabled.
4. **Given** an invalid edited configuration, **When** the user attempts to
   apply it, **Then** the application reports the error and blocks application.
5. **Given** pending edits and an external modification to the same file,
   **When** the application detects the change, **Then** it asks before
   discarding pending edits and reloading the external version; if the user
   declines, it keeps the draft and blocks application until the conflict is
   resolved.
6. **Given** a supported setting whose value comes from a shared variable,
   **When** the user edits it, **Then** the application shows affected uses and
   offers to edit the variable or only the selected setting.
7. **Given** a supported setting in an included file, **When** the user edits
   it, **Then** the application identifies and edits its actual source file.

### User Story 2 - Install an i3 Desktop (Priority: P1)

A user selects the supported components they need, reviews the proposed
installation, and installs missing dependencies from distribution repositories
or curated upstream source.

**Why this priority**: A working desktop and its dependencies are essential to
the product's setup workflow.

**Independent Test**: On a supported distribution in an existing graphical
session, select components with missing dependencies, review the plan, and
install them; verify that the resulting component status is reported accurately.

**Acceptance Scenarios**:

1. **Given** an existing system, **When** the user opens setup, **Then** the
   application identifies the supported platform and reports installed and
   missing selected components.
2. **Given** an installation choice, **When** both repository and curated
   source options are supported, **Then** the user can choose the desired source.
3. **Given** a proposed installation, **When** the user reviews it, **Then**
   the plan identifies package operations, source builds, and operations requiring
   elevation before the user approves execution.
4. **Given** a missing privilege or a failed operation, **When** installation
   cannot continue, **Then** the application reports the failure and resulting
   state without claiming success or changing administrator-group membership.

### User Story 3 - Preview and Apply Desktop Changes (Priority: P1)

A user adjusts a visual or behavioral setting, previews it on the running desktop
where feasible, and decides whether to keep it.

**Why this priority**: Visual feedback and recovery are central to customizing a
working desktop safely.

**Independent Test**: Change a supported previewable setting, allow the
confirmation timer to expire, and verify that the previous configuration and
desktop state are restored.

**Acceptance Scenarios**:

1. **Given** a valid change with live-preview support, **When** preview starts,
   **Then** the running desktop reflects the change and a confirmation timer is
   shown.
2. **Given** an active preview, **When** the user confirms within the time
   limit, **Then** the change is kept.
3. **Given** an active preview, **When** the time limit expires without
   confirmation, **Then** the previous state is restored.
4. **Given** a change that cannot be previewed live, **When** the user selects
   it, **Then** the application explains the limitation and offers an explicit
   apply workflow requiring confirmation.
5. **Given** an active preview, **When** the user cancels or the GUI crashes
   without confirmation, **Then** the prior state is restored immediately on
   cancellation or after the timeout on a crash.

### User Story 4 - Customize the Rice (Priority: P2)

A user customizes the existing component stack using extensive visual controls,
including a shared palette that keeps supported components consistent.

**Why this priority**: This turns the installer into a useful desktop
customization tool while building on safe editing and application.

**Independent Test**: Change a shared palette color and an individual component
setting, then verify the affected supported configurations and running
components reflect the chosen values.

**Acceptance Scenarios**:

1. **Given** a supported shared color, **When** the user changes it and applies
   the change, **Then** the selected color is propagated to its supported uses
   across the configured components.
2. **Given** an editable numeric or color setting, **When** an appropriate
   control is available, **Then** the user can adjust it using a slider or color
   picker and see the relevant configuration code.
3. **Given** a setting in source-built st that requires recompilation, **When**
   the user changes it, **Then** the application explains the build requirement
   and reports the result of applying it.

### User Story 5 - Restore and Transfer a Setup (Priority: P2)

A user restores an earlier configuration or exports a reusable profile containing
configuration and explicitly selected assets.

**Why this priority**: Recovery protects existing setups; profiles make the
customized rice reusable across machines.

**Independent Test**: Apply a configuration change and restore its backup;
separately export and import a profile with a selected wallpaper and verify its
configuration and asset are available for review.

**Acceptance Scenarios**:

1. **Given** an application-managed configuration change, **When** the user
   restores its backup, **Then** the earlier configuration is recovered.
2. **Given** a customized setup and explicitly selected assets, **When** the
   user exports a profile, **Then** the profile contains its configuration and
   those assets.
3. **Given** a profile to import, **When** the user opens it, **Then** they can
   review its contents before it changes the target setup.
4. **Given** an imported profile with commands or executable configuration,
   **When** the user reviews it, **Then** those entries are identified for
   explicit review before any application or execution.
5. **Given** a profile with missing components or unresolved paths, **When**
   it is imported, **Then** the user can resolve paths and separately review
   any offered installation plan.

### Edge Cases

- An existing config uses includes, variables, duplicate directives, or syntax
  the application cannot safely associate with a control.
- A file changes outside the application while edits or a live preview are
  pending; the user declines to discard pending edits.
- Validation tooling is unavailable, or a component cannot validate its config
  without starting or reloading it.
- The application exits or crashes during a live preview; the timer expires
  while the GUI is unresponsive.
- A monitor, resolution, scaling, or compositor change makes the desktop
  difficult to see or use.
- A package is unavailable, a source build fails, network access is interrupted,
  or a package manager is already in use.
- A source-built component requires recompilation or a restart rather than an
  immediate reload.
- Importing a profile encounters missing components, incompatible paths,
  existing configurations, or assets unavailable on the target machine.
- Restoring a backup conflicts with changes made since the backup was created.

## Requirements

### Functional Requirements

**Platform and setup**

- **FR-001**: The application MUST run from an existing graphical Linux session
  before or after the user switches to i3.
- **FR-002**: The first release MUST support current supported releases of
  representative distributions across the existing apt, dnf, pacman, zypper,
  and apk families. The exact distribution and version matrix requires agreement.
- **FR-003**: The application MUST identify supported components and their
  installation status and report unsupported or unknown environments clearly.
- **FR-004**: The application MUST let users select supported components and,
  where supported, choose between distribution packages and curated upstream
  source builds.
- **FR-005**: Source builds MUST be limited to a curated list of supported
  components and upstream sources.
- **FR-006**: Before installation, the application MUST present a plan including
  package operations, source builds, and elevated operations, and obtain user
  approval.
- **FR-007**: The application MUST NOT modify administrator-group membership.
  It MUST report when required privileges are unavailable.
- **FR-008**: Installation MUST report progress, failures, and the resulting
  state, including partial completion; it MUST NOT report a failed operation as
  successful.
- **FR-009**: The GUI workflow MUST replace the existing standalone shell
  installer; reuse of its implementation is a technical-planning decision.

**Configuration and controls**

- **FR-010**: The application MUST detect and preserve existing configurations,
  including unrelated and unsupported content, rather than silently replacing
  them with generated defaults.
- **FR-011**: For supported settings, the application MUST show the relevant
  original configuration code alongside the GUI controls and support two-way
  synchronization between controls and manual code edits. It MUST also provide
  a full-file editor with navigation to the relevant setting.
- **FR-012**: When existing content cannot be safely interpreted or modified,
  the application MUST preserve it, warn the user, and disable only controls
  that cannot operate safely.
- **FR-013**: The application MUST offer extensive controls for the existing
  stack: i3, Polybar, Rofi, Picom, Dunst, wallpaper, st, fonts and scaling,
  display arrangement, keyboard shortcuts, and workspaces.
- **FR-014**: Initial settings MUST include i3 gaps, borders, workspaces and
  keybindings; Polybar modules and layout; Rofi theme; Picom opacity and
  shadows; Dunst appearance; wallpaper; st colors and fonts; scaling; and
  display arrangement. Detailed supported settings require feature-level
  specifications.
- **FR-015**: The application MUST provide suitable sliders, color pickers, and
  other controls, as appropriate to each supported setting.
- **FR-016**: The application MUST provide a shared palette editor that applies
  supported colors consistently across applicable components. The existing
  Catppuccin Mocha rice is the starting preset.
- **FR-017**: The application MUST validate changes before applying them, report
  validation errors, and block application of configuration known to be invalid.
  If reliable validation is unavailable, it MUST explain the limitation and
  require explicit confirmation before applying.
- **FR-018**: If external changes are detected while edits are pending, the
  application MUST ask before discarding those edits and reloading the external
  file. If the user declines, the application MUST retain the draft and block
  application until the conflict is resolved.
- **FR-019**: Where a setting requires rebuilding a component, including
  source-built st, the application MUST explain this requirement and report
  build and application results.

**Preview and recovery**

- **FR-020**: Where feasible, the application MUST preview changes on the
  running desktop before the user commits them; otherwise it MUST explain the
  limitation and require confirmation before applying the change.
- **FR-021**: Live previews MUST automatically revert to the prior state if the
  user does not confirm within a visible 30-second timeout. Users MUST also be
  able to cancel and revert immediately. Timed recovery MUST operate
  independently of the GUI so that it still works if the GUI crashes or becomes
  unresponsive.
- **FR-022**: The application MUST back up configuration changes and provide a
  way to restore earlier configuration. It MUST report package changes
  separately; package rollback is not required.
- **FR-023**: The application MUST avoid silently overwriting external changes
  during preview, apply, or restore. Conflict-resolution details require
  agreement.

**Profiles**

- **FR-024**: Users MUST be able to save, export, and import profiles containing
  configuration and explicitly selected assets such as wallpapers and fonts.
- **FR-025**: Profile import MUST show contents for review before changing the
  target setup and MUST report missing or incompatible dependencies and assets.
  Commands and executable configuration MUST be identified for explicit review
  before application or execution.
- **FR-026**: The first release MUST support the existing component stack;
  replacement components and alternative window managers are outside its scope.
- **FR-027**: Before profile export, the application MUST warn about potentially
  sensitive configuration and let the user review and exclude files or values.
- **FR-028**: Profiles MUST use portable references where possible and prompt
  users to resolve missing machine-specific paths during import.
- **FR-029**: When an imported asset conflicts with an existing file, the
  application MUST let the user keep the existing file, rename the imported
  asset, or replace the existing file.
- **FR-030**: When an imported profile requires missing components, the
  application MUST offer a separate installation plan for review rather than
  install them as part of import without approval.
- **FR-031**: When a supported setting derives from a shared variable, the
  application MUST show affected uses and let the user choose to edit the
  variable or only that setting.
- **FR-032**: The application MUST support editing recognized settings in
  included configuration files, showing and changing the actual source file
  while preserving content it cannot safely interpret.
- **FR-033**: Backups MUST be kept in the user's state directory under
  `i3-rice/backups`, retaining the 20 most recent backups per configuration
  file.
- **FR-034**: If the current file differs from the expected version, restore
  MUST be blocked until the user reviews the conflict and explicitly chooses
  how to proceed.

### Key Entities

- **Component**: A supported desktop element, its installation state, available
  installation sources, and applicable configuration.
- **Configuration document**: An existing or newly created component
  configuration, including content the application may not understand.
- **Setting**: A supported user-adjustable value and its relationship to one or
  more configuration locations.
- **Palette**: Shared color values and their supported component-specific uses.
- **Installation plan**: Selected components and proposed package, source-build,
  and elevated operations.
- **Preview**: A temporary applied change, its prior state, and its confirmation
  deadline.
- **Backup**: Recoverable earlier configuration associated with a change.
- **Profile**: A saved configuration and explicitly selected assets for reuse.

## Success Criteria

### Measurable Outcomes

- **SC-001**: On each distribution in the agreed support matrix, a user can
  review and execute a setup plan and see the outcome of every requested
  component operation.
- **SC-002**: In acceptance tests covering each first-release component, a
  supported GUI edit and a supported manual code edit both synchronize correctly
  and preserve unrelated configuration.
- **SC-003**: In preview acceptance tests, every unconfirmed preview reverts
  after its configured timeout, including the agreed failure scenarios.
- **SC-004**: An exported profile with selected assets can be reviewed and
  imported on another supported installation without silently overwriting
  existing configuration.
- **SC-005**: A user can restore a backed-up configuration after an
  application-managed change.

## Assumptions

- The primary audience is technical Linux users comfortable with i3 and
  configuration files.
- The first release targets i3 on X11, matching the existing project. Other
  window managers and Wayland support are outside the first release.
- The application is written in Python; the GUI library will be chosen during
  technical planning.
- A graphical session and network access for online installation are available;
  unavailable connectivity must be reported.
- This is an umbrella specification. Detailed feature specifications will
  define component settings, supported distributions, validation, profile
  compatibility, preview recovery, and acceptance coverage.

## Open Questions

- Which exact distribution releases and component versions form the support
  matrix, and how long are they supported?
- How are preview and restore conflicts resolved?
- Which settings can be previewed safely, and how does automatic recovery work
  if the graphical session itself fails?
- How should profiles handle incompatible or differing component versions?
- Which syntax and included-file patterns can be synchronized reliably, and
  which validators are available for each component?
- What installation sources and version-selection rules belong in the curated
  catalog, and which actions require separate confirmation?
- What are the exact component-specific control lists and measurable usability
  targets for the first release?
