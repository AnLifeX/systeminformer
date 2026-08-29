/*
 * Copyright (c) 2022 Winsider Seminars & Solutions, Inc.  All rights reserved.
 *
 * This file is part of System Informer.
 *
 * Authors:
 *
 *     dmex    2016-2026
 *
 */

#include "updater.h"

static TASKDIALOG_BUTTON DownloadButtonArray[] =
{
    { IDOK, L"Download" }
};

static TASKDIALOG_BUTTON PortableButtonArray[] =
{
    { IDOK, L"Open releases" }
};

/**
 * \brief Callback procedure for the Update Available task dialog page.
 * \param WindowHandle Handle to the dialog window.
 * \param WindowMessage The window message.
 * \param wParam Additional message-specific information.
 * \param lParam Additional message-specific information.
 * \param dwRefData The updater context.
 * \return HRESULT Successful or errant status.
 */
HRESULT CALLBACK ShowAvailableCallbackProc(
    _In_ HWND WindowHandle,
    _In_ UINT WindowMessage,
    _In_ WPARAM wParam,
    _In_ LPARAM lParam,
    _In_ LONG_PTR dwRefData
    )
{
    PPH_UPDATER_CONTEXT context = (PPH_UPDATER_CONTEXT)dwRefData;

    switch (WindowMessage)
    {
    case TDN_NAVIGATED:
        PhSetEvent(&InitializedEvent);
        break;
    case TDN_BUTTON_CLICKED:
        {
            if ((INT)wParam == IDOK)
            {
                if (context->PortableMode)
                {
                    PhShellExecute(WindowHandle, UPDATE_RELEASES_URL, NULL);
                    return S_OK;
                }

                ShowProgressDialog(context);
                return S_FALSE;
            }
        }
        break;
    case TDN_HYPERLINK_CLICKED:
        {
            TaskDialogLinkClicked(context);
            return S_FALSE;
        }
        break;
    }

    return S_OK;
}

/**
 * \brief Shows the Update Available dialog page.
 * \param Context The updater context.
 */
VOID ShowAvailableDialog(
    _In_ PPH_UPDATER_CONTEXT Context
    )
{
    TASKDIALOGCONFIG config;

    memset(&config, 0, sizeof(TASKDIALOGCONFIG));
    config.cbSize = sizeof(TASKDIALOGCONFIG);
    config.dwFlags = TDF_USE_HICON_MAIN | TDF_ALLOW_DIALOG_CANCELLATION | TDF_CAN_BE_MINIMIZED | TDF_ENABLE_HYPERLINKS;
    config.dwCommonButtons = TDCBF_CANCEL_BUTTON;
    config.hMainIcon = PhGetApplicationIcon(FALSE, Context->WindowDpi);
    config.cxWidth = 200;
    if (Context->PortableMode)
    {
        config.pButtons = PortableButtonArray;
        config.cButtons = RTL_NUMBER_OF(PortableButtonArray);
    }
    else
    {
        config.pButtons = DownloadButtonArray;
        config.cButtons = RTL_NUMBER_OF(DownloadButtonArray);
    }
    config.lpCallbackData = (LONG_PTR)Context;
    config.pfCallback = ShowAvailableCallbackProc;

    config.pszWindowTitle = L"System Informer - Updater";
    if (Context->SwitchingChannel)
    {
        switch (Context->Channel)
        {
        case PhReleaseChannel:
            config.pszMainInstruction = L"Would you like to download the Release build?";
            break;
        //case PhPreviewChannel:
        //    config.pszMainInstruction = L"Would you like to download the Preview build?";
        //    break;
        case PhCanaryChannel:
            config.pszMainInstruction = L"Would you like to download the Canary build?";
            break;
        //case PhDeveloperChannel:
        //    config.pszMainInstruction = L"Would you like to download the Developer build?";
        //    break;
        default:
            config.pszMainInstruction = L"Would you like to download the update?";
            break;
        }
    }
    else
    {
        config.pszMainInstruction = L"A newer build of System Informer is available.";
    }

    if (Context->PortableMode)
    {
        config.pszContent = PhaFormatString(
            L"Version: %s\r\n\r\nPortable builds are updated manually. Open the release page to download the latest ZIP.\r\n\r\n<A HREF=\"changelog.txt\">View the changelog</A>",
            PhGetStringOrEmpty(Context->Version)
            )->Buffer;
    }
    else
    {
        config.pszContent = PhaFormatString(
            L"Version: %s\r\nDownload size: %s\r\n\r\n<A HREF=\"changelog.txt\">View the changelog</A>",
            PhGetStringOrEmpty(Context->Version),
            PhGetStringOrEmpty(Context->SetupFileLength)
            )->Buffer;
    }

    PhTaskDialogNavigatePage(Context->DialogHandle, &config);
}
