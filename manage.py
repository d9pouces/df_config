#  This file is part of Interdiode
#   Copyright (c) 2020-2023 Matthieu Gallet <matthieu.gallet@19pouces.net>
#   All Rights Reserved
"""manage script for development purpose."""

from df_config.manage import manage

if __name__ == "__main__":
    manage("df_config", settings_module="test_df_config.data.settings")
