////////////////////////////////////////////////////////////////////////////////
// This file is part of df_config                                              /
//                                                                             /
// Copyright (C) 2020 Matthieu Gallet <github@19pouces.net>                    /
// All Rights Reserved                                                         /
//                                                                             /
// You may use, distribute and modify this code under the                      /
// terms of the (BSD-like) CeCILL-B license.                                   /
//                                                                             /
// You should have received a copy of the CeCILL-B license with                /
// this file. If not, please visit:                                            /
// https://cecill.info/licences/Licence_CeCILL-B_V1-en.txt (English)           /
// or https://cecill.info/licences/Licence_CeCILL-B_V1-fr.txt (French)         /
//                                                                             /
////////////////////////////////////////////////////////////////////////////////


export function documentLoad(evt: Event) {
    /* Define a new event 'DOMContentAdded' and call it when DOMContentLoaded is fired.

    This event can also be fired when new HTML content is added in the page, by websocket or AJAX requests.

    * Avoid to directly use DOMNodeInserted or MutationObserver (both are too frequently called, so we avoid
    to add receivers on it).
    * */

    const newEvent = new Event('DOMContentAdded');
    evt.target.dispatchEvent(newEvent);
}

document.addEventListener("DOMContentLoaded", documentLoad);