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

'use strict';

const path = require('path');

module.exports = {
    entry: {
        "df_config": ['./df_config/app.ts'],
    },
    resolve: {
        extensions: ['.ts', '.js', '.json']
    },
    output: {
        path: path.resolve(__dirname, '../'),
        filename: '[name]/static/js/[name].min.js'
    },
    plugins: [],

    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: 'ts-loader',
                exclude: /node_modules/,
            },
            {
                test: /\.scss$/,
                exclude: /node_modules/,
                use: [
                    {
                        loader: 'file-loader',
                        options: {outputPath: '.', name: '[folder]/static/css/[folder].min.css'}
                    },
                    'sass-loader'
                ]
            }
        ]
    },
    // Useful for debugging.
    devtool: 'source-map',
    performance: {hints: false}
};