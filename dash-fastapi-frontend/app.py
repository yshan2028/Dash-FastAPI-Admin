import dash
import feffery_antd_components as fac
import feffery_utils_components as fuc
from dash import dcc, html
from dash.dependencies import Input, Output, State
from flask import session
from api.login import LoginApi
from api.router import RouterApi
from callbacks import app_c  # noqa: F401
from config.env import AppConfig
from config.global_config import RouterConfig
from server import app
from store.store import render_store_container
from utils.cache_util import CacheManager
from utils.router_util import RouterUtil
from utils.tree_tool import find_key_by_href, find_node_values
from views import forget, layout, login, page_404


app.layout = html.Div(
    [
        # 注入url监听
        fuc.FefferyLocation(id='url-container'),
        # 用于回调pathname信息
        dcc.Location(id='dcc-url', refresh=False),
        # 注入js执行容器
        fuc.FefferyExecuteJs(id='execute-js-container'),
        # 注入页面内容挂载点
        html.Div(id='app-mount'),
        # 注入全局配置容器
        fac.AntdConfigProvider(id='app-config-provider'),
        # 注入快捷搜索面板
        fuc.FefferyShortcutPanel(
            id='search-panel',
            data=[],
            placeholder='输入你想要搜索的菜单...',
            panelStyles={'accentColor': '#1890ff', 'zIndex': 99999},
        ),
        # 辅助处理多输入 -> 存储接口返回token校验信息
        render_store_container(),
        # 重定向容器
        html.Div(id='redirect-container'),
        # 登录消息失效对话框提示
        fac.AntdModal(
            html.Div(
                [
                    fac.AntdIcon(
                        icon='fc-high-priority', style={'font-size': '28px'}
                    ),
                    fac.AntdText(
                        '登录状态已过期，您可以继续留在该页面，或者重新登录',
                        style={'margin-left': '5px'},
                    ),
                ]
            ),
            id='token-invalid-modal',
            visible=False,
            title='系统提示',
            okText='重新登录',
            renderFooter=True,
            centered=True,
        ),
        # 注入全局消息提示容器
        html.Div(id='global-message-container'),
        # 注入全局通知信息容器
        html.Div(id='global-notification-container'),
    ]
)


@app.callback(
    output=dict(
        app_mount=Output('app-mount', 'children'),
        redirect_container=Output(
            'redirect-container', 'children', allow_duplicate=True
        ),
        menu_current_key=Output('current-key-container', 'data'),
        search_panel_data=Output('search-panel', 'data'),
    ),
    inputs=dict(pathname=Input('url-container', 'pathname')),
    state=dict(
        url_trigger=State('url-container', 'trigger'),
        session_token=State('token-container', 'data'),
    ),
    prevent_initial_call=True,
)
def router(pathname, url_trigger, session_token):
    """
    全局路由回调
    """
    # 检查当前会话是否已经登录
    token_result = session.get('Authorization')
    # 若已登录
    if token_result and session_token and token_result == session_token:
        if url_trigger == 'load':
            current_user = LoginApi.get_info()
            router_list_result = RouterApi.get_routers()
            router_list = router_list_result['data']
            menu_info = RouterUtil.generate_menu_tree(router_list)
            # search_panel_data = get_search_panel_data(user_menu_list)
            search_panel_data = []
            session['user_info'] = current_user['user']
            permissions = {
                'perms': current_user['permissions'],
                'roles': current_user['roles'],
            }
            cache_obj = dict(
                user_info=current_user['user'],
                permissions=permissions,
                menu_info=menu_info,
                search_panel_data=search_panel_data,
            )
            CacheManager.set(cache_obj)
        menu_info = CacheManager.get('menu_info')
        search_panel_data = CacheManager.get('search_panel_data')
        dynamic_valid_pathname_list = find_node_values(menu_info, 'href')
        valid_href_list = (
            dynamic_valid_pathname_list + RouterConfig.STATIC_VALID_PATHNAME
        )
        if pathname in valid_href_list:
            current_key = find_key_by_href(menu_info, pathname)
            if pathname == '/':
                current_key = '首页'
            if pathname == '/user/profile':
                current_key = '个人资料'
            if url_trigger == 'load':
                # 根据pathname控制渲染行为
                if pathname == '/login' or pathname == '/forget':
                    # 重定向到主页面
                    return dict(
                        app_mount=dash.no_update,
                        redirect_container=dcc.Location(
                            pathname='/', id='router-redirect'
                        ),
                        menu_current_key={'current_key': current_key},
                        search_panel_data=search_panel_data,
                    )

                user_menu_info = RouterUtil.generate_menu_tree(
                    RouterUtil.get_visible_routers(router_list)
                )
                # 否则正常渲染主页面
                return dict(
                    app_mount=layout.render_content(user_menu_info),
                    redirect_container=None,
                    menu_current_key={'current_key': current_key},
                    search_panel_data=search_panel_data,
                )

            else:
                return dict(
                    app_mount=dash.no_update,
                    redirect_container=None,
                    menu_current_key={'current_key': current_key},
                    search_panel_data=search_panel_data,
                )

        else:
            # 渲染404状态页
            return dict(
                app_mount=page_404.render_content(),
                redirect_container=None,
                menu_current_key=dash.no_update,
                search_panel_data=dash.no_update,
            )

    else:
        # 若未登录
        # 根据pathname控制渲染行为
        # 检验pathname合法性
        if pathname not in RouterConfig.BASIC_VALID_PATHNAME:
            # 渲染404状态页
            return dict(
                app_mount=page_404.render_content(),
                redirect_container=None,
                menu_current_key=dash.no_update,
                search_panel_data=dash.no_update,
            )

        if pathname == '/login':
            return dict(
                app_mount=login.render_content(),
                redirect_container=None,
                menu_current_key=dash.no_update,
                search_panel_data=dash.no_update,
            )

        if pathname == '/forget':
            return dict(
                app_mount=forget.render_forget_content(),
                redirect_container=None,
                menu_current_key=dash.no_update,
                search_panel_data=dash.no_update,
            )

        # 否则重定向到登录页
        return dict(
            app_mount=dash.no_update,
            redirect_container=dcc.Location(
                pathname='/login', id='router-redirect'
            ),
            menu_current_key=dash.no_update,
            search_panel_data=dash.no_update,
        )


if __name__ == '__main__':
    app.run(
        host=AppConfig.app_host,
        port=AppConfig.app_port,
        debug=AppConfig.app_debug,
    )
