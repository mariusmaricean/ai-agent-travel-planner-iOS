import SwiftUI

struct AccountView: View {
    @ObservedObject var viewModel: AgentViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeader(
                title: "Account",
                subtitle: viewModel.accountSubtitle
            )

            HStack(spacing: 12) {
                Image(systemName: viewModel.isSignedIn ? "person.crop.circle.badge.checkmark" : "person.crop.circle")
                    .foregroundStyle(TravelPlannerColor.teal)
                    .frame(width: 38, height: 38)
                    .background(TravelPlannerColor.tealSoft, in: Circle())

                VStack(alignment: .leading, spacing: 4) {
                    Text(viewModel.accountTitle)
                        .font(.subheadline.weight(.semibold))
                    Text(viewModel.isSignedIn ? "Authenticated traveler scope" : "Device traveler scope")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(12)
            .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))

            if viewModel.isSignedIn {
                Button(role: .destructive) {
                    viewModel.signOutAccount()
                } label: {
                    Label("Sign out", systemImage: "rectangle.portrait.and.arrow.right")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            } else {
                VStack(spacing: 10) {
                    TextField("Email", text: $viewModel.accountEmail)
                        .keyboardType(.emailAddress)
                        .textContentType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .padding(12)
                        .background(.white, in: RoundedRectangle(cornerRadius: 12, style: .continuous))

                    TextField("Display name", text: $viewModel.accountDisplayName)
                        .textContentType(.name)
                        .padding(12)
                        .background(.white, in: RoundedRectangle(cornerRadius: 12, style: .continuous))

                    SecureField("Password", text: $viewModel.accountPassword)
                        .textContentType(.password)
                        .padding(12)
                        .background(.white, in: RoundedRectangle(cornerRadius: 12, style: .continuous))

                    HStack(spacing: 10) {
                        Button {
                            Task {
                                await viewModel.loginAccount()
                            }
                        } label: {
                            Label("Sign in", systemImage: "person.crop.circle.badge.checkmark")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(TravelPlannerColor.teal)

                        Button {
                            Task {
                                await viewModel.registerAccount()
                            }
                        } label: {
                            Label("Create", systemImage: "person.badge.plus")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                    }
                    .disabled(viewModel.isAuthenticating)
                }
            }

            if let accountMessage = viewModel.accountMessage {
                Text(accountMessage)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(14)
        .background(.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}
